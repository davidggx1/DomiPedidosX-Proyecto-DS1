"""
Asignación automática de repartidor (HU-36).

Cuando cocina pasa un pedido a "Listo para despacho", el sistema le asigna un
repartidor sin que el operador intervenga.

Regla de elección (criterios 1 y 4):
1. Solo cuentan los repartidores de la sede del pedido, activos y "Disponible".
2. Gana el que tenga MENOS entregas en curso.
3. Si empatan, gana el que lleva MÁS TIEMPO esperando: el que entregó su último
   pedido hace más tiempo. Quien nunca ha entregado va primero.
4. Si aún empatan, el de menor id, para que el resultado sea siempre el mismo.

Nota: con la regla de HU-35 (un repartidor libre no tiene otra entrega en curso)
todos los candidatos que pasan la validación tienen 0 entregas activas, así que en
la práctica decide el desempate. Se deja el orden por carga por si el equipo
decide permitir varias entregas por repartidor.

Si no hay nadie libre (criterio 2), el pedido queda "Sin asignar" y el operador
lo ve resaltado en el módulo de logística para asignarlo a mano (HU-35).

Las reglas de validación son las mismas de la asignación manual (pedidos/asignacion.py).
"""
import logging

from django.conf import settings
from django.db.models import Count, F, Max, Q
from django.dispatch import receiver

from usuarios.models import Repartidor

from .asignacion import ESTADOS_EN_CURSO, AsignacionInvalida, asignar
from .estados import estado_pedido_cambiado
from .models import EstadoPedido, OrigenPedido

logger = logging.getLogger(__name__)

# Errores del repartidor: se prueba con el siguiente candidato.
# Cualquier otro error es del pedido (ya tiene repartidor, ya no está listo...): se para.
ERRORES_DEL_REPARTIDOR = {
    "otra_sede",
    "repartidor_inactivo",
    "repartidor_no_disponible",
    "repartidor_ocupado",
}


def esta_activa():
    """Interruptor general. En settings: ASIGNACION_AUTOMATICA_REPARTIDOR = False para apagarla."""
    return getattr(settings, "ASIGNACION_AUTOMATICA_REPARTIDOR", True)


def candidatos(sede_id):
    """Repartidores que podrían recibir el pedido, en orden de prioridad."""
    return (
        Repartidor.objects.filter(
            empleado__sede_id=sede_id,
            empleado__usuario__is_active=True,
            disponible=True,
        )
        .annotate(
            entregas_activas=Count(
                "pedidos_asignados",
                filter=Q(pedidos_asignados__estado__in=ESTADOS_EN_CURSO),
                distinct=True,
            ),
            ultima_entrega=Max(
                "pedidos_asignados__historial_estados__fecha_hora",
                filter=Q(pedidos_asignados__historial_estados__estado=EstadoPedido.ENTREGADO),
            ),
        )
        .order_by("entregas_activas", F("ultima_entrega").asc(nulls_first=True), "pk")
    )


def necesita_repartidor(pedido):
    return (
        pedido.estado == EstadoPedido.LISTO_DESPACHO
        and pedido.origen != OrigenPedido.MOSTRADOR
        and pedido.repartidor_id is None
    )


def asignar_automaticamente(pedido):
    """
    Busca el mejor repartidor libre y se lo asigna al pedido.
    Devuelve el repartidor asignado, o None si el pedido queda "Sin asignar".
    """
    if not necesita_repartidor(pedido):
        return None

    for repartidor in candidatos(pedido.sede_id):
        try:
            asignar(pedido, repartidor, usuario=None, automatica=True)
        except AsignacionInvalida as error:
            if error.codigo in ERRORES_DEL_REPARTIDOR:
                # Otro proceso lo ocupó entre la consulta y el bloqueo: siguiente candidato.
                continue
            logger.info("Pedido %s no se asignó automáticamente: %s", pedido.pk, error.mensaje)
            return None
        logger.info("Pedido %s asignado automáticamente al repartidor %s", pedido.pk, repartidor.pk)
        return repartidor

    logger.info("Pedido %s queda sin asignar: no hay repartidores libres en la sede", pedido.pk)
    return None


@receiver(estado_pedido_cambiado)
def asignar_al_quedar_listo(sender, pedido, estado_anterior, usuario, **kwargs):
    """Se dispara cuando cocina marca el pedido "Listo para despacho" (criterio 1).

    Corre después de guardar el cambio de estado: si algo falla aquí, el cambio de
    cocina ya quedó hecho y el pedido sigue disponible para asignarlo a mano.
    """
    if pedido.estado != EstadoPedido.LISTO_DESPACHO or not esta_activa():
        return
    try:
        asignar_automaticamente(pedido)
    except Exception:
        logger.exception("Falló la asignación automática del pedido %s", pedido.pk)
