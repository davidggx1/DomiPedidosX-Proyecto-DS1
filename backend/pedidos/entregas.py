"""
Entregas del repartidor (HU-42, HU-43 y HU-45).

- El repartidor solo ve los pedidos asignados a él (pedidos_visibles).
- Solo aparecen los que están en curso (por recoger, recogidos o en camino):
  al entregarse o cancelarse salen solos de la lista (HU-42, criterio 3).
- Avanza la entrega en orden estricto: recogido → en camino → entregado
  (la secuencia la valida pedidos/estados.py). Si el cliente paga en efectivo,
  al entregar registra cuánto recibió y la factura queda pagada (HU-45).
"""
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework import generics, serializers, status
from rest_framework.response import Response
from rest_framework.views import APIView

from usuarios.permissions import EsRepartidor
from usuarios.roles import REPARTIDOR

from .asignacion import ESTADOS_EN_CURSO
from .estados import TransicionInvalida, cambiar_estado
from .models import EstadoFactura, EstadoPedido, Factura
from .serializers import DetalleEntregaSerializer, TarjetaEntregaSerializer, cobrar_en_efectivo
from .views import pedidos_visibles

# Pasos que da el repartidor (HU-45).
ESTADOS_DE_ENTREGA = [EstadoPedido.RECOGIDO, EstadoPedido.EN_CAMINO, EstadoPedido.ENTREGADO]


def entregas_del_repartidor(usuario):
    return (
        pedidos_visibles(usuario, REPARTIDOR)
        .select_related("cliente", "factura", "sede__ciudad")
        .prefetch_related(
            "detalles__producto",
            "detalles__producto_tamano",
            "detalles__combo",
            "detalles__adiciones__adicion",
            "detalles__exclusiones",
        )
    )


def entregas_en_curso(usuario):
    return entregas_del_repartidor(usuario).filter(estado__in=ESTADOS_EN_CURSO)


class EntregaInvalida(Exception):
    """El recaudo no es válido. `mensaje` se puede mostrar al repartidor."""

    def __init__(self, mensaje, codigo):
        super().__init__(mensaje)
        self.mensaje = mensaje
        self.codigo = codigo


def validar_recaudo(pedido, estado_nuevo, monto_recaudado):
    """Al entregar un pedido en efectivo pendiente, el monto es obligatorio y cubre el total."""
    if estado_nuevo != EstadoPedido.ENTREGADO or not cobrar_en_efectivo(pedido):
        return
    if monto_recaudado is None:
        raise EntregaInvalida("Escribe cuánto dinero recibiste del cliente.", "monto_obligatorio")
    if monto_recaudado < pedido.factura.total:
        raise EntregaInvalida(
            "El monto recibido no alcanza para pagar el total del pedido.", "monto_insuficiente"
        )


def actualizar_entrega(pedido, estado_nuevo, usuario, monto_recaudado=None):
    """
    Da el siguiente paso de la entrega. Si es la entrega de un pedido en efectivo,
    registra el recaudo y deja la factura pagada; todo o nada.
    """
    validar_recaudo(pedido, estado_nuevo, monto_recaudado)
    cobrar = estado_nuevo == EstadoPedido.ENTREGADO and cobrar_en_efectivo(pedido)
    with transaction.atomic():
        pedido = cambiar_estado(pedido, estado_nuevo, usuario, REPARTIDOR)
        if cobrar:
            Factura.objects.filter(pedido=pedido).update(
                monto_recaudado=monto_recaudado,
                fecha_recaudo=timezone.now(),
                recaudado_por_id=pedido.repartidor_id,
                estado_factura=EstadoFactura.PAGADA,
            )
    return pedido


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


class ActualizarEntregaSerializer(serializers.Serializer):
    estado = serializers.ChoiceField(
        choices=[(estado.value, estado.label) for estado in ESTADOS_DE_ENTREGA],
        error_messages={
            "required": "Indica el nuevo estado de la entrega.",
            "invalid_choice": "El repartidor solo marca recogido, en camino o entregado.",
        },
    )
    monto_recaudado = serializers.DecimalField(
        max_digits=12, decimal_places=2, min_value=0, required=False, allow_null=True,
        error_messages={"min_value": "El monto no puede ser negativo."},
    )


class ActualizarEntregaView(APIView):
    """
    PATCH /api/pedidos/mis-entregas/<id>/entrega/
    {"estado": "entregado", "monto_recaudado": "50000"}

    Responde el detalle actualizado de la entrega. Un pedido de otro repartidor responde 404.
    """

    permission_classes = [EsRepartidor]

    @extend_schema(request=ActualizarEntregaSerializer, responses=DetalleEntregaSerializer)
    def patch(self, request, pk):
        pedido = get_object_or_404(entregas_en_curso(request.user), pk=pk)
        datos = ActualizarEntregaSerializer(data=request.data)
        datos.is_valid(raise_exception=True)

        try:
            actualizar_entrega(
                pedido,
                datos.validated_data["estado"],
                request.user,
                datos.validated_data.get("monto_recaudado"),
            )
        except EntregaInvalida as error:
            return Response(
                {"monto_recaudado": error.mensaje, "codigo": error.codigo},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except TransicionInvalida as error:
            return Response(
                {"detail": error.mensaje, "codigo": error.codigo}, status=status.HTTP_400_BAD_REQUEST
            )

        pedido = entregas_del_repartidor(request.user).get(pk=pk)
        return Response(DetalleEntregaSerializer(pedido, context={"rol": REPARTIDOR}).data)
