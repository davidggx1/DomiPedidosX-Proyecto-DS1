"""Puente entre la máquina de estados y los grupos WebSocket de cocina."""
import logging

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.dispatch import receiver

from .estados import estado_pedido_cambiado

logger = logging.getLogger(__name__)


@receiver(estado_pedido_cambiado)
def publicar_cambio_en_cocina(sender, pedido, estado_anterior, usuario, **kwargs):
    """Publica el cambio en la sede y en el grupo global de administradores."""
    capa = get_channel_layer()
    if capa is None:
        return

    evento = {
        "type": "pedido.actualizado",
        "pedido_id": pedido.pk,
        "sede_id": pedido.sede_id,
        "estado": pedido.estado,
        "estado_anterior": estado_anterior,
    }
    try:
        async_to_sync(capa.group_send)(f"cocina_sede_{pedido.sede_id}", evento)
        async_to_sync(capa.group_send)("cocina_todas_sedes", evento)
    except Exception:
        # El cambio de estado ya quedó guardado; una caída de Redis no debe
        # convertir una operación confirmada en un error HTTP engañoso.
        logger.exception("No fue posible publicar el cambio del pedido %s por WebSocket.", pedido.pk)
