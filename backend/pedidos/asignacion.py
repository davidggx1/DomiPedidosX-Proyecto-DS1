"""
Asignación de repartidores a pedidos (HU-35).

Reglas:
- Solo se asignan pedidos "Listo para despacho" (HU-31, criterio 2).
- Los pedidos de mostrador o para llevar no llevan repartidor (HU-24, criterio 3).
- El repartidor debe ser de la misma sede, tener la cuenta activa y estar
  "Disponible" (HU-41) y libre: sin otra entrega en curso (HU-35, criterio 3).
- Un pedido tiene un solo repartidor; para cambiarlo, primero se retira la
  asignación (criterio 4). Solo se retira antes de que lo recoja.

La asignación automática (HU-36) puede reutilizar `repartidor_libre` y `asignar`.
"""
from django.db import transaction
from django.dispatch import Signal

from usuarios.models import Repartidor

from .models import EstadoPedido, OrigenPedido, Pedido

# Pedidos que ocupan a un repartidor (también se usa en HU-41 para contar sus entregas).
ESTADOS_EN_CURSO = [EstadoPedido.LISTO_DESPACHO, EstadoPedido.RECOGIDO, EstadoPedido.EN_CAMINO]

# Se envía al confirmar la transacción. Argumentos: pedido, repartidor (None si se retiró), usuario.
asignacion_cambiada = Signal()


class AsignacionInvalida(Exception):
    """La asignación no está permitida. `mensaje` se puede mostrar al usuario."""

    def __init__(self, mensaje, codigo, campo="detail"):
        super().__init__(mensaje)
        self.mensaje = mensaje
        self.codigo = codigo
        self.campo = campo


def repartidor_libre(repartidor, excepto_pedido=None):
    """True si no tiene otra entrega en curso."""
    otros = repartidor.pedidos_asignados.filter(estado__in=ESTADOS_EN_CURSO)
    if excepto_pedido is not None:
        otros = otros.exclude(pk=excepto_pedido.pk)
    return not otros.exists()


def validar_asignacion(pedido, repartidor):
    """Lanza AsignacionInvalida si no se puede asignar. No guarda nada."""
    if pedido.estado != EstadoPedido.LISTO_DESPACHO:
        raise AsignacionInvalida(
            'Solo se asignan pedidos en "Listo para despacho".', "pedido_no_listo"
        )
    if pedido.origen == OrigenPedido.MOSTRADOR:
        raise AsignacionInvalida(
            "Los pedidos de mostrador no llevan repartidor.", "pedido_sin_domicilio"
        )
    if pedido.repartidor_id is not None:
        raise AsignacionInvalida(
            "El pedido ya tiene repartidor. Retira primero la asignación para cambiarlo.",
            "pedido_ya_asignado",
        )
    if repartidor.empleado.sede_id != pedido.sede_id:
        raise AsignacionInvalida(
            "El repartidor no pertenece a la sede del pedido.", "otra_sede", "repartidor"
        )
    if not repartidor.empleado.usuario.is_active:
        raise AsignacionInvalida(
            "La cuenta del repartidor está desactivada.", "repartidor_inactivo", "repartidor"
        )
    if not repartidor.disponible:
        raise AsignacionInvalida(
            'El repartidor está "No disponible".', "repartidor_no_disponible", "repartidor"
        )
    if not repartidor_libre(repartidor, excepto_pedido=pedido):
        raise AsignacionInvalida(
            "El repartidor ya está realizando otra entrega.", "repartidor_ocupado", "repartidor"
        )


def _avisar(pedido, repartidor, usuario):
    transaction.on_commit(
        lambda: asignacion_cambiada.send(
            sender=Pedido, pedido=pedido, repartidor=repartidor, usuario=usuario
        )
    )


def asignar(pedido, repartidor, usuario=None):
    """Asigna el repartidor al pedido. Bloquea ambas filas para evitar asignaciones dobles."""
    with transaction.atomic():
        pedido = Pedido.objects.select_for_update().get(pk=pedido.pk)
        repartidor = (
            Repartidor.objects.select_for_update()
            .select_related("empleado__usuario")
            .get(pk=repartidor.pk)
        )
        validar_asignacion(pedido, repartidor)
        pedido.repartidor = repartidor
        pedido.save(update_fields=["repartidor"])
        _avisar(pedido, repartidor, usuario)
    return pedido


def retirar(pedido, usuario=None):
    """Quita el repartidor asignado, solo si todavía no recogió el pedido."""
    with transaction.atomic():
        pedido = Pedido.objects.select_for_update().get(pk=pedido.pk)
        if pedido.repartidor_id is None:
            raise AsignacionInvalida("El pedido no tiene repartidor asignado.", "sin_asignacion")
        if pedido.estado != EstadoPedido.LISTO_DESPACHO:
            raise AsignacionInvalida(
                "El repartidor ya recogió el pedido; no se puede retirar la asignación.",
                "pedido_recogido",
            )
        pedido.repartidor = None
        pedido.save(update_fields=["repartidor"])
        _avisar(pedido, None, usuario)
    return pedido
