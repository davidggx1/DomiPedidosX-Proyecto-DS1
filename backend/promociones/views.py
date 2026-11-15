from drf_spectacular.utils import OpenApiParameter, extend_schema_view, extend_schema
from rest_framework import viewsets

from usuarios.permissions import filtrar_por_sede, rol_requerido
from usuarios.roles import ADMINISTRADOR, OPERADOR

from .models import EstadoPromocion, Promocion
from .serializers import PromocionSerializer


@extend_schema_view(
    list=extend_schema(
        parameters=[
            OpenApiParameter(
                "estado",
                str,
                enum=[estado.value for estado in EstadoPromocion],
                description="vigente, programada, vencida o inactiva. Sin valor: todas.",
            ),
            OpenApiParameter("activa", bool, description="true: solo activas · false: solo inactivas."),
        ]
    )
)
class PromocionViewSet(viewsets.ModelViewSet):
    """
    HU-84: crear, editar y desactivar promociones.

    El operador gestiona las de su sede; el administrador, las de todas.
    DELETE desactiva (borrado lógico): la promoción deja de poder usarse, pero se conserva
    para el historial. Editar no cambia las compras ya hechas: cada factura guarda su
    descuento al momento de la compra.
    """

    serializer_class = PromocionSerializer
    permission_classes = [rol_requerido(OPERADOR, ADMINISTRADOR)]
    pagination_class = None
    http_method_names = ["get", "post", "patch", "put", "delete", "head", "options"]

    def get_queryset(self):
        promociones = filtrar_por_sede(
            Promocion.objects.select_related("sede").order_by("-fecha_inicio", "nombre", "id"),
            self.request.user,
        )
        estado = self.request.query_params.get("estado")
        if estado:
            promociones = promociones.con_estado(estado)
        activa = self.request.query_params.get("activa")
        if activa is not None:
            promociones = promociones.filter(activa=activa.lower() in ("true", "1"))
        return promociones

    def perform_destroy(self, instance):
        instance.activa = False
        instance.save(update_fields=["activa"])