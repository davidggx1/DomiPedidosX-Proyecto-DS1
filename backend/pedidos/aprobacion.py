"""Aprobación de pedidos entrantes (HU-28)."""
from django.db import transaction
from rest_framework.exceptions import APIException, NotFound

from usuarios.permissions import filtrar_por_sede

from .eventos import notificar_pedido
from .models import EstadoPedido, HistorialEstadoPedido, Pedido


class PedidoYaProcesado(APIException):
    status_code = 409
    default_code = "pedido_ya_procesado"

    def __init__(self, estado_actual):
        self.detail = {
            "detail": "Este pedido ya no está pendiente de aprobación.",
            "estado_actual": estado_actual,
        }


@transaction.atomic
def aprobar_pedido(*, usuario, pedido_id):
    """Pasa el pedido de 'pendiente_aprobacion' a 'recibido'.

    Devuelve (pedido, registro_de_historial).
    """
    # El administrador ve todo; el operador solo su sede (404 si es de otra).
    visibles = filtrar_por_sede(Pedido.objects.all(), usuario)
    pedido = visibles.select_for_update().filter(pk=pedido_id).first()
    if pedido is None:
        raise NotFound("Pedido no encontrado.")

    if pedido.estado != EstadoPedido.PENDIENTE_APROBACION:
        raise PedidoYaProcesado(pedido.estado)

    pedido.estado = EstadoPedido.RECIBIDO
    pedido.save(update_fields=["estado"])

    registro = HistorialEstadoPedido.objects.create(
        pedido=pedido,
        usuario=usuario,
        estado=EstadoPedido.RECIBIDO,
        observacion="Pedido aprobado por el operador.",
    )

    # Sale por WebSocket al confirmarse la transacción (on_commit).
    notificar_pedido(pedido)
    return pedido, registro