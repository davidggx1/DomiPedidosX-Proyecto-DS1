"""
Entregas del repartidor (HU-42 y HU-43).

- El repartidor solo ve los pedidos asignados a él (pedidos_visibles).
- Solo aparecen los que están en curso (por recoger, recogidos o en camino):
  al entregarse o cancelarse salen solos de la lista (HU-42, criterio 3).
"""
from rest_framework import generics

from usuarios.permissions import EsRepartidor
from usuarios.roles import REPARTIDOR

from .asignacion import ESTADOS_EN_CURSO
from .serializers import DetalleEntregaSerializer, TarjetaEntregaSerializer
from .views import pedidos_visibles


def entregas_en_curso(usuario):
    return (
        pedidos_visibles(usuario, REPARTIDOR)
        .filter(estado__in=ESTADOS_EN_CURSO)
        .select_related("cliente", "factura")
        .prefetch_related(
            "detalles__producto",
            "detalles__producto_tamano",
            "detalles__combo",
            "detalles__adiciones__adicion",
            "detalles__exclusiones",
        )
    )


class EntregasMixin:
    permission_classes = [EsRepartidor]
    pagination_class = None

    def get_queryset(self):
        return entregas_en_curso(self.request.user).order_by("fecha_creacion", "id")

    def get_serializer_context(self):
        return {**super().get_serializer_context(), "rol": REPARTIDOR}


class MisEntregasView(EntregasMixin, generics.ListAPIView):
    """
    GET /api/pedidos/mis-entregas/

    Pedidos en curso asignados al repartidor, del más antiguo al más nuevo (HU-42).
    """

    serializer_class = TarjetaEntregaSerializer


class DetalleEntregaView(EntregasMixin, generics.RetrieveAPIView):
    """
    GET /api/pedidos/mis-entregas/<id>/

    Dirección, productos, totales y método de pago de una entrega en curso (HU-43).
    Un pedido de otro repartidor responde 404.
    """

    serializer_class = DetalleEntregaSerializer
