"""
HU-66 · Historial completo de pedidos (administrador).

- GET /api/pedidos/historial/        Todos los pedidos de todas las sedes, del más
                                     reciente al más antiguo, paginados.
- GET /api/pedidos/historial/<id>/   Ficha técnica: marcas de tiempo de cada cambio
                                     de estado, quién lo hizo y el motivo si se canceló.

Solo el administrador puede verlo (criterio 3). La búsqueda con filtros (HU-68)
se construye sobre este listado: basta con filtrar `HistorialPedidosView.get_queryset`.
"""
from django.db.models import Prefetch
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema, extend_schema_field
from rest_framework import generics, serializers
from rest_framework.pagination import PageNumberPagination

from usuarios.permissions import rol_requerido
from usuarios.roles import ADMINISTRADOR

from .models import HistorialEstadoPedido, Pedido
from .serializers import HistorialEstadoSerializer, PedidoEntranteSerializer

def dinero():
    """Un campo de dinero nuevo cada vez: DRF no permite compartir una instancia de campo."""
    return serializers.DecimalField(max_digits=12, decimal_places=2, allow_null=True)


class PaginacionHistorial(PageNumberPagination):
    """20 pedidos por página; se pueden pedir hasta 100 con ?tamano=."""

    page_size = 20
    page_size_query_param = "tamano"
    max_page_size = 100


# --- Listado (criterio 1) -----------------------------------------------------------


class SedeResumidaSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    nombre = serializers.CharField()


class FilaHistorialPedidoSerializer(serializers.ModelSerializer):
    """Una fila del historial: número, fecha, sede, cliente, estado y total."""

    sede = SedeResumidaSerializer(read_only=True)
    cliente = serializers.SerializerMethodField()
    estado_nombre = serializers.CharField(source="get_estado_display", read_only=True)
    total = serializers.SerializerMethodField()

    class Meta:
        model = Pedido
        fields = [
            "id", "numero_pedido", "fecha_creacion", "sede", "cliente",
            "estado", "estado_nombre", "origen", "total",
        ]

    def get_cliente(self, pedido) -> str | None:
        """Nombre del cliente; null en un pedido de mostrador sin cliente registrado."""
        cliente = pedido.cliente
        return f"{cliente.nombres} {cliente.apellidos}" if cliente else None

    @extend_schema_field(dinero())
    def get_total(self, pedido):
        """Total facturado; null si el pedido no tiene factura."""
        factura = getattr(pedido, "factura", None)
        return factura.total if factura else None


# --- Ficha técnica (criterio 2) -----------------------------------------------------


class PasoHistorialSerializer(HistorialEstadoSerializer):
    """Un cambio de estado, con los minutos que pasaron desde el anterior."""

    minutos_desde_anterior = serializers.SerializerMethodField()

    class Meta(HistorialEstadoSerializer.Meta):
        fields = [*HistorialEstadoSerializer.Meta.fields, "minutos_desde_anterior"]

    def get_minutos_desde_anterior(self, paso) -> int | None:
        anterior = getattr(paso, "anterior", None)
        if anterior is None:
            return None
        return round((paso.fecha_hora - anterior.fecha_hora).total_seconds() / 60)


class FacturaFichaSerializer(serializers.Serializer):
    numero = serializers.CharField()
    metodo_pago = serializers.CharField()
    estado_factura = serializers.CharField()
    subtotal = dinero()
    costo_domicilio = dinero()
    valor_descuento = dinero()
    total = dinero()


class FichaPedidoSerializer(FilaHistorialPedidoSerializer):
    """Todo lo de la fila más el detalle técnico del pedido."""

    historial = serializers.SerializerMethodField()
    factura = serializers.SerializerMethodField()
    repartidor = serializers.SerializerMethodField()
    detalles = serializers.SerializerMethodField()

    class Meta(FilaHistorialPedidoSerializer.Meta):
        fields = [
            *FilaHistorialPedidoSerializer.Meta.fields,
            "motivo_cancelacion", "descripcion", "tiempo_estimado_entrega",
            "entrega_direccion", "entrega_barrio", "entrega_indicaciones",
            "repartidor", "asignacion_automatica", "factura", "detalles", "historial",
        ]

    @extend_schema_field(PasoHistorialSerializer(many=True))
    def get_historial(self, pedido):
        pasos = list(pedido.historial_estados.all())
        for anterior, paso in zip([None, *pasos], pasos):
            paso.anterior = anterior
        return PasoHistorialSerializer(pasos, many=True).data

    @extend_schema_field(FacturaFichaSerializer(allow_null=True))
    def get_factura(self, pedido):
        factura = getattr(pedido, "factura", None)
        return FacturaFichaSerializer(factura).data if factura else None

    def get_repartidor(self, pedido) -> str | None:
        if pedido.repartidor_id is None:
            return None
        empleado = pedido.repartidor.empleado
        return f"{empleado.nombres} {empleado.apellidos}"

    @extend_schema_field(serializers.ListField(child=serializers.DictField()))
    def get_detalles(self, pedido):
        # Mismo formato de líneas que ve el operador en pedidos entrantes (HU-27).
        return PedidoEntranteSerializer().get_detalles(pedido)


# --- Vistas -------------------------------------------------------------------------


def pedidos_del_historial():
    return Pedido.objects.select_related("sede", "cliente", "factura").order_by("-fecha_creacion", "-pk")


_SOLO_ADMIN = OpenApiResponse(description="No inició sesión o no es administrador.")


@extend_schema(
    tags=["Pedidos"],
    summary="Historial completo de pedidos (HU-66)",
    description=(
        "Todos los pedidos de todas las sedes, del más reciente al más antiguo, en páginas "
        "de 20. Usa `?page=2` para la siguiente página y `?tamano=50` para cambiar el tamaño "
        "(máximo 100). Solo administrador."
    ),
    parameters=[
        OpenApiParameter("page", int, description="Número de página (desde 1)."),
        OpenApiParameter("tamano", int, description="Pedidos por página (por defecto 20, máximo 100)."),
    ],
    responses={200: FilaHistorialPedidoSerializer(many=True), 403: _SOLO_ADMIN},
)
class HistorialPedidosView(generics.ListAPIView):
    permission_classes = [rol_requerido(ADMINISTRADOR)]
    serializer_class = FilaHistorialPedidoSerializer
    pagination_class = PaginacionHistorial

    def get_queryset(self):
        return pedidos_del_historial()


@extend_schema(
    tags=["Pedidos"],
    summary="Ficha técnica de un pedido (HU-66)",
    description=(
        "Marcas de tiempo de cada cambio de estado (con quién lo hizo y los minutos desde el "
        "paso anterior), motivo de cancelación, factura, repartidor y productos. Solo administrador."
    ),
    responses={200: FichaPedidoSerializer, 403: _SOLO_ADMIN, 404: OpenApiResponse(description="El pedido no existe.")},
)
class FichaPedidoView(generics.RetrieveAPIView):
    permission_classes = [rol_requerido(ADMINISTRADOR)]
    serializer_class = FichaPedidoSerializer

    def get_queryset(self):
        historial = HistorialEstadoPedido.objects.select_related("usuario").order_by("fecha_hora", "pk")
        return pedidos_del_historial().select_related("repartidor__empleado").prefetch_related(
            Prefetch("historial_estados", queryset=historial),
            "detalles__producto",
            "detalles__producto_tamano",
            "detalles__combo",
            "detalles__adiciones__adicion",
            "detalles__exclusiones",
        )
