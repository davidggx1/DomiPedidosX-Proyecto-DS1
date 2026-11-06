from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.dispatch import receiver

from .estados import estado_pedido_cambiado


@receiver(estado_pedido_cambiado)
def publicar_cambio_estado(sender, pedido, estado_anterior, usuario, **kwargs):
    payload = {
        'tipo': 'estado_pedido_cambiado',
        'pedido_id': pedido.pk,
        'numero_pedido': pedido.numero_pedido,
        'estado_anterior': estado_anterior,
        'estado': pedido.estado,
        'usuario_id': usuario.pk if usuario else None,
    }
    async_to_sync(get_channel_layer().group_send)(
        f'pedido_{pedido.pk}',
        {'type': 'estado_pedido_cambiado', 'payload': payload},
    )
