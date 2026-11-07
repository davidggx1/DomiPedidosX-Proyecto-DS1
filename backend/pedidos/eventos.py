import logging

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.db import transaction

from .consumers import GRUPO_ADMIN, grupo_sede
from .models import EstadoPedido
from .serializers import PedidoEntranteSerializer, pedidos_con_detalle

logger = logging.getLogger(__name__)


def notificar_pedido(pedido):
    """Avisa por WebSocket a la sede del pedido (y al administrador).

    Se envía al confirmarse la transacción, para que el pedido ya tenga detalles.
    Un fallo del canal nunca debe romper la creación del pedido.
    """
    pedido_id, sede_id = pedido.pk, pedido.sede_id

    def _enviar():
        try:
            actual = pedidos_con_detalle().get(pk=pedido_id)
            tipo = (
                "pedido_nuevo"
                if actual.estado == EstadoPedido.PENDIENTE_APROBACION
                else "pedido_actualizado"
            )
            evento = {
                "type": "pedido.evento",
                "data": {"tipo": tipo, "pedido": PedidoEntranteSerializer(actual).data},
            }
            layer = get_channel_layer()
            for grupo in (grupo_sede(sede_id), GRUPO_ADMIN):
                async_to_sync(layer.group_send)(grupo, evento)
        except Exception:
            logger.exception("No se pudo notificar el pedido %s", pedido_id)

    transaction.on_commit(_enviar)