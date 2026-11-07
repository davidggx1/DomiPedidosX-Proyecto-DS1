"""
Seguimiento del pedido por el cliente (HU-47).

- GET /api/pedidos/mios/ lista los pedidos del cliente: primero los que siguen
  en curso y luego los cerrados, del más nuevo al más viejo.
- El estado actual y el historial de un pedido salen de GET /api/pedidos/<id>/estado/.
- Los cambios llegan en tiempo real por ws/pedidos/<id>/estado/ (EstadoPedidoConsumer).
"""
from django.db.models import Case, IntegerField, Value, When
from rest_framework import generics, serializers

from usuarios.permissions import EsCliente

from .estados import CLIENTE, ESTADOS_FINALES
from .models import Pedido
from .serializers import nombre_linea
from .views import pedidos_visibles

# Cuántos pedidos muestra la lista (los en curso siempre caben primero).
LIMITE_PEDIDOS = 30


class PedidoClienteSerializer(serializers.ModelSerializer):
    estado_nombre = serializers.CharField(source="get_estado_display", read_only=True)
    total = serializers.DecimalField(
        source="factura.total", max_digits=12, decimal_places=2, read_only=True, default=None
    )
    resumen = serializers.SerializerMethodField()

    class Meta:
        model = Pedido
        fields = ["id", "numero_pedido", "estado", "estado_nombre", "fecha_creacion", "total", "resumen"]

    def get_resumen(self, pedido) -> list[str]:
        return [f"{d.cantidad}x {nombre_linea(d)}" for d in pedido.detalles.all()]


class MisPedidosView(generics.ListAPIView):
    """GET /api/pedidos/mios/"""

    serializer_class = PedidoClienteSerializer
    permission_classes = [EsCliente]
    pagination_class = None

    def get_queryset(self):
        cerrado = Case(
            When(estado__in=ESTADOS_FINALES, then=Value(1)), default=Value(0), output_field=IntegerField()
        )
        return (
            pedidos_visibles(self.request.user, CLIENTE)
            .select_related("factura")
            .prefetch_related("detalles__producto", "detalles__producto_tamano", "detalles__combo")
            .annotate(cerrado=cerrado)
            .order_by("cerrado", "-fecha_creacion", "-id")[:LIMITE_PEDIDOS]
        )
