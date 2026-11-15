"""
HU-25 · El cliente cancela su pedido antes de que entre a preparación.

- Solo en "Pendiente de aprobación" o "Recibido" (criterios 1 y 2); la regla
  vive en la tabla TRANSICIONES de estados.py.
- En la misma transacción: cambia el estado (queda en el historial como
  "Cancelado", criterio 4) y devuelve el stock retenido (criterio 3).
- El cupo de la sede se libera solo: la capacidad cuenta los pedidos
  "recibido" y "en preparación", y el cupo de combos ignora los cancelados.
- El correo de cancelación lo envía pedidos/correos.py (HU-50) al cambiar el estado.
"""
import logging

from django.db import transaction
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from usuarios.permissions import EsCliente

from .estados import CLIENTE, ESTADOS_FINALES, TransicionInvalida, cambiar_estado, siguientes_estados
from .models import EstadoPedido, Notificacion, TipoNotificacion
from .serializers import EstadoPedidoSerializer
from .stock import reintegrar_stock
from .views import pedidos_visibles

logger = logging.getLogger(__name__)

MOTIVO_CLIENTE = "Cancelado por el cliente."


def cancelar_pedido_cliente(pedido, usuario):
    """Cancela el pedido del cliente, devuelve el stock y avisa. Lanza TransicionInvalida."""
    if pedido.estado not in ESTADOS_FINALES and EstadoPedido.CANCELADO not in siguientes_estados(
        pedido.estado, CLIENTE
    ):
        raise TransicionInvalida(
            f'Tu pedido ya está "{pedido.get_estado_display()}" y no se puede cancelar. '
            "Comunícate con la sede si necesitas ayuda.",
            "cancelacion_no_permitida",
        )

    with transaction.atomic():
        pedido = cambiar_estado(pedido, EstadoPedido.CANCELADO, usuario=usuario, rol=CLIENTE, motivo=MOTIVO_CLIENTE)
        reintegrar_stock(pedido)
        Notificacion.objects.create(
            usuario=usuario,
            pedido=pedido,
            mensaje=f"Cancelaste el pedido {pedido.numero_pedido}.",
            tipo=TipoNotificacion.PEDIDO_CANCELADO,
        )
    return pedido


class CancelarPedidoView(APIView):
    """POST /api/pedidos/<id>/cancelar/ · El cliente cancela su pedido (HU-25)."""

    permission_classes = [EsCliente]

    @extend_schema(request=None, responses=EstadoPedidoSerializer)
    def post(self, request, pk):
        pedido = get_object_or_404(
            pedidos_visibles(request.user, CLIENTE).select_related("cliente__usuario", "sede"), pk=pk
        )
        try:
            pedido = cancelar_pedido_cliente(pedido, request.user)
        except TransicionInvalida as error:
            return Response({"detail": error.mensaje, "codigo": error.codigo}, status=status.HTTP_400_BAD_REQUEST)
        pedido.refresh_from_db()
        return Response(EstadoPedidoSerializer(pedido, context={"rol": CLIENTE}).data)
