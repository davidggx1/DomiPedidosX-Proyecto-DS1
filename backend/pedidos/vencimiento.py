"""
SCRUM-119 · Liberar los cupos de los pedidos que la sede nunca aprobó.

Un pedido "Pendiente de aprobación" ya ocupa un cupo de capacidad de la sede
(HU-61) y retiene su stock (HU-15). Si nadie lo aprueba, ese cupo y ese stock
quedarían ocupados para siempre. Cuando un pedido lleva más de
PEDIDO_PENDIENTE_MINUTOS esperando:

- se cancela con un motivo que lo explica (queda en el historial),
- se devuelve el stock y el cupo de combos (lo mismo que la cancelación del cliente, HU-25),
- el cupo de capacidad se libera solo, porque los cancelados no cuentan,
- el cliente recibe una notificación y un correo.

Lo ejecuta cada minuto la tarea periódica `pedidos.tasks.vencer_pedidos_pendientes`.
Sin Celery beat se puede ejecutar a mano: `python manage.py vencer_pedidos_pendientes`.
"""
import logging
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from usuarios.roles import ADMINISTRADOR
from usuarios.tasks import encolar_correo

from .estados import TransicionInvalida, cambiar_estado
from .models import EstadoPedido, Notificacion, Pedido, TipoNotificacion
from .stock import reintegrar_stock

logger = logging.getLogger(__name__)


def motivo_vencimiento(minutos):
    return f"Cancelado automáticamente: la sede no lo aprobó en {minutos} minutos."


def pedidos_vencidos(ahora=None):
    minutos = settings.PEDIDO_PENDIENTE_MINUTOS
    if minutos <= 0:
        return Pedido.objects.none()
    limite = (ahora or timezone.now()) - timedelta(minutes=minutos)
    return Pedido.objects.filter(
        estado=EstadoPedido.PENDIENTE_APROBACION, fecha_creacion__lt=limite
    ).order_by("fecha_creacion")


def _avisar_al_cliente(pedido, motivo):
    cliente = pedido.cliente
    if cliente is None:
        return
    Notificacion.objects.create(
        usuario=cliente.usuario,
        pedido=pedido,
        mensaje=f"Tu pedido {pedido.numero_pedido} fue cancelado porque la sede no lo aprobó a tiempo.",
        tipo=TipoNotificacion.PEDIDO_CANCELADO,
    )
    mensaje = "\n".join([
        f"Hola {cliente.nombres},",
        "",
        f"Tu pedido {pedido.numero_pedido} de {pedido.sede.nombre} fue cancelado porque la sede "
        f"no lo aprobó en {settings.PEDIDO_PENDIENTE_MINUTOS} minutos.",
        "No se te cobrará nada. Puedes volver a pedir cuando quieras.",
        "",
        "DomiPedidosX",
    ])
    transaction.on_commit(
        lambda: encolar_correo(f"Pedido {pedido.numero_pedido} cancelado", mensaje, [cliente.usuario.email])
    )


def vencer_pendientes(ahora=None):
    """Cancela los pedidos pendientes vencidos. Devuelve cuántos canceló."""
    motivo = motivo_vencimiento(settings.PEDIDO_PENDIENTE_MINUTOS)
    cancelados = 0
    for pk in pedidos_vencidos(ahora).values_list("pk", flat=True):
        try:
            with transaction.atomic():
                pedido = (
                    Pedido.objects.select_for_update(of=("self",))
                    .select_related("cliente__usuario", "sede")
                    .get(pk=pk)
                )
                # Con la fila bloqueada: si el operador lo aprobó justo ahora, ya no
                # está pendiente y se deja como está (el administrador sí podría
                # cancelar un pedido recibido, así que no basta con cambiar_estado).
                if pedido.estado != EstadoPedido.PENDIENTE_APROBACION:
                    continue
                pedido = cambiar_estado(
                    pedido, EstadoPedido.CANCELADO, usuario=None, rol=ADMINISTRADOR, motivo=motivo
                )
                reintegrar_stock(pedido)
                _avisar_al_cliente(pedido, motivo)
        except TransicionInvalida:
            continue
        except Exception:
            logger.exception("No se pudo vencer el pedido %s", pk)
            continue
        cancelados += 1

    if cancelados:
        logger.info("Se cancelaron %s pedidos pendientes que la sede no aprobó a tiempo", cancelados)
    return cancelados
