from drf_spectacular.utils import OpenApiParameter, extend_schema_view, extend_schema
from django.db import transaction
from rest_framework import viewsets

from usuarios.permissions import filtrar_por_sede, rol_requerido
from usuarios.roles import ADMINISTRADOR, OPERADOR, obtener_rol, obtener_sede

from .models import Combo, ComboSede, EstadoPromocion, Promocion
from .serializers import ComboSerializer, PromocionSerializer


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


class ComboViewSet(viewsets.ModelViewSet):
    """
    HU-85: crear, editar y desactivar combos.

    El operador gestiona los de su sede; el administrador, los de todas (`?sede=` filtra).
    DELETE desactiva (borrado lógico). Editar no cambia los pedidos ya hechos.
    """

    serializer_class = ComboSerializer
    permission_classes = [rol_requerido(OPERADOR, ADMINISTRADOR)]
    pagination_class = None
    http_method_names = ["get", "post", "patch", "put", "delete", "head", "options"]

    def _sede_operador(self):
        usuario = self.request.user
        return obtener_sede(usuario) if obtener_rol(usuario) != ADMINISTRADOR else None

    def get_serializer_context(self):
        contexto = super().get_serializer_context()
        contexto["sede"] = self._sede_operador()
        return contexto

    def get_queryset(self):
        combos = Combo.objects.prefetch_related("sedes_disponibles__sede").order_by(
            "-fecha_inicio", "nombre", "id"
        )
        if obtener_rol(self.request.user) == ADMINISTRADOR:
            sede = self.request.query_params.get("sede")
        else:
            sede = getattr(self._sede_operador(), "pk", 0)
        if sede:
            combos = combos.filter(sedes_disponibles__sede_id=sede)
        elif obtener_rol(self.request.user) != ADMINISTRADOR:
            return combos.none()
        activo = self.request.query_params.get("activo")
        if activo is not None:
            combos = combos.filter(activo=activo.lower() in ("true", "1"))
        return combos

    @transaction.atomic
    def perform_destroy(self, instance):
        instance.activo = False
        instance.save(update_fields=["activo"])
        ComboSede.objects.filter(combo=instance).update(activo=False)