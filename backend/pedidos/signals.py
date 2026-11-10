import logging

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.dispatch import receiver
from django.utils import timezone

from .asignacion import asignacion_cambiada
from .consumers import grupo_repartidor
from .estados import estado_pedido_cambiado
from .models import EstadoPedido

logger = logging.getLogger(__name__)


@receiver(estado_pedido_cambiado)
def publicar_cambio_estado(sender, pedido, estado_anterior, usuario, **kwargs):
    payload = {
        'tipo': 'estado_pedido_cambiado',
        'pedido_id': pedido.pk,
        'numero_pedido': pedido.numero_pedido,
        'estado_anterior': estado_anterior,
        'estado': pedido.estado,
        'usuario_id': usuario.pk if usuario else None,
        # Para que el seguimiento del cliente (HU-47) se actualice sin volver a consultar.
        'estado_nombre': pedido.get_estado_display(),
        'motivo_cancelacion': pedido.motivo_cancelacion,
        'fecha_hora': timezone.now().isoformat(),
    }
    async_to_sync(get_channel_layer().group_send)(
        f'pedido_{pedido.pk}',
        {'type': 'estado_pedido_cambiado', 'payload': payload},
    )


# --- Repartidor: su lista de entregas en tiempo real (HU-42) y avisos (HU-40) ----


def aviso_asignado(pedido):
    """HU-40, criterio 1: aviso de pantalla y sonido cuando le asignan un pedido."""
    return {
        'tipo': 'asignado',
        'numero_pedido': pedido.numero_pedido,
        'mensaje': f'Te asignaron el pedido {pedido.numero_pedido}. Ve a la sede a recogerlo.',
    }


def aviso_retirado(pedido, motivo):
    """HU-40, criterio 3: el pedido sale de su lista porque lo reasignaron o lo cancelaron."""
    if motivo == 'cancelado':
        mensaje = f'El pedido {pedido.numero_pedido} fue cancelado. Ya no debes entregarlo.'
    else:
        mensaje = f'El pedido {pedido.numero_pedido} fue retirado de tu lista.'
    return {
        'tipo': 'retirado',
        'motivo': motivo,
        'numero_pedido': pedido.numero_pedido,
        'mensaje': mensaje,
    }


def avisar_repartidor(repartidor_id, pedido_id, aviso=None):
    """Le dice a la app del repartidor que vuelva a pedir su lista.

    `aviso` (HU-40) es el mensaje que la app muestra en pantalla con sonido; si no
    viene, el cambio es silencioso (p. ej. el mismo repartidor avanzó la entrega).
    Un fallo del canal nunca debe romper la asignación ni el cambio de estado.
    """
    data = {'tipo': 'entregas_actualizadas', 'pedido_id': pedido_id}
    if aviso is not None:
        data['aviso'] = aviso
    try:
        async_to_sync(get_channel_layer().group_send)(
            grupo_repartidor(repartidor_id),
            {'type': 'entregas.evento', 'data': data},
        )
    except Exception:
        logger.exception('No se pudo avisar al repartidor %s', repartidor_id)


@receiver(asignacion_cambiada)
def avisar_asignacion(sender, pedido, repartidor, usuario, repartidor_anterior=None, **kwargs):
    """Al asignar avisa al nuevo repartidor; al retirar, al que lo tenía."""
    if repartidor is not None:
        avisar_repartidor(repartidor.pk, pedido.pk, aviso_asignado(pedido))
    if repartidor_anterior is not None:
        avisar_repartidor(repartidor_anterior.pk, pedido.pk, aviso_retirado(pedido, 'reasignado'))


@receiver(estado_pedido_cambiado)
def avisar_cambio_estado_al_repartidor(sender, pedido, estado_anterior, usuario, **kwargs):
    """Si el pedido ya tiene repartidor, su tarjeta cambia o sale de la lista.

    Si lo cancelaron, además le llega el aviso de retiro (HU-40, criterio 3).
    """
    if pedido.repartidor_id is None:
        return
    aviso = aviso_retirado(pedido, 'cancelado') if pedido.estado == EstadoPedido.CANCELADO else None
    avisar_repartidor(pedido.repartidor_id, pedido.pk, aviso)
