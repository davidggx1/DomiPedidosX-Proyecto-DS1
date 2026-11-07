import logging

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.dispatch import receiver
from django.utils import timezone

from .asignacion import asignacion_cambiada
from .consumers import grupo_repartidor
from .estados import estado_pedido_cambiado

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


# --- Repartidor: su lista de entregas en tiempo real (HU-42) ---------------------


def avisar_repartidor(repartidor_id, pedido_id):
    """Le dice a la app del repartidor que vuelva a pedir su lista.

    Un fallo del canal nunca debe romper la asignación ni el cambio de estado.
    """
    try:
        async_to_sync(get_channel_layer().group_send)(
            grupo_repartidor(repartidor_id),
            {
                'type': 'entregas.evento',
                'data': {'tipo': 'entregas_actualizadas', 'pedido_id': pedido_id},
            },
        )
    except Exception:
        logger.exception('No se pudo avisar al repartidor %s', repartidor_id)


@receiver(asignacion_cambiada)
def avisar_asignacion(sender, pedido, repartidor, usuario, repartidor_anterior=None, **kwargs):
    """Al asignar avisa al nuevo repartidor; al retirar, al que lo tenía."""
    for afectado in (repartidor, repartidor_anterior):
        if afectado is not None:
            avisar_repartidor(afectado.pk, pedido.pk)


@receiver(estado_pedido_cambiado)
def avisar_cambio_estado_al_repartidor(sender, pedido, estado_anterior, usuario, **kwargs):
    """Si el pedido ya tiene repartidor, su tarjeta cambia o sale de la lista."""
    if pedido.repartidor_id is not None:
        avisar_repartidor(pedido.repartidor_id, pedido.pk)
