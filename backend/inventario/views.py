"""HU-14 · API de existencias. Los listados y cambios quedan acotados a la sede del usuario."""
from drf_spectacular.utils import OpenApiParameter, extend_schema, extend_schema_view
from rest_framework import viewsets
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from menu.disponibilidad import sedes_que_gestiona
from menu.permissions import EsPersonalDeMenu

from .alertas import datos_alerta
from .models import AlertaInventario, InventarioInsumo, InventarioProducto
from .serializers import InventarioInsumoSerializer, InventarioProductoSerializer

PARAMETRO_SEDE = OpenApiParameter("sede", int, description="Filtra por id de sede.")


class InventarioBaseViewSet(viewsets.ModelViewSet):
    permission_classes = [EsPersonalDeMenu]
    modelo = None
    campo_item = None

    def get_queryset(self):
        gestionables = sedes_que_gestiona(self.request.user)
        queryset = self.modelo.objects.select_related("sede", self.campo_item).order_by(
            "sede__nombre", f"{self.campo_item}__nombre", "id"
        )
        if gestionables is not None:
            queryset = queryset.filter(sede_id__in=gestionables)

        sede = self.request.query_params.get("sede")
        if sede not in (None, "") and self.action == "list":
            try:
                queryset = queryset.filter(sede_id=int(sede))
            except ValueError:
                raise ValidationError({"sede": "La sede debe ser un id numérico."})
        return queryset

    def create(self, request, *args, **kwargs):
        # Un operador sin sede asignada no puede registrar nada, sin importar el cuerpo.
        if sedes_que_gestiona(request.user) == set():
            raise PermissionDenied("No tienes una sede asignada.")
        return super().create(request, *args, **kwargs)


@extend_schema_view(list=extend_schema(parameters=[PARAMETRO_SEDE]))
class InventarioProductoViewSet(InventarioBaseViewSet):
    serializer_class = InventarioProductoSerializer
    modelo = InventarioProducto
    campo_item = "producto"


@extend_schema_view(list=extend_schema(parameters=[PARAMETRO_SEDE]))
class InventarioInsumoViewSet(InventarioBaseViewSet):
    serializer_class = InventarioInsumoSerializer
    modelo = InventarioInsumo
    campo_item = "insumo"


class AlertasInventarioView(APIView):
    """
    GET /api/inventario/alertas/ (HU-16)

    Low stock alerts of the sede of the operator (an admin sees all, or one with
    ?sede=<id>). ?estado=activa (default), resuelta (the last 50) or todas
    """

    permission_classes = [EsPersonalDeMenu]

    @extend_schema(
        parameters=[
            PARAMETRO_SEDE,
            OpenApiParameter("estado", str, enum=["activa", "resuelta", "todas"]),
        ],
        responses={200: None},
    )
    def get(self, request):
        estado = request.query_params.get("estado", "activa")
        if estado not in ("activa", "resuelta", "todas"):
            raise ValidationError({"estado": "Usa activa, resuelta o todas."})

        alertas = AlertaInventario.objects.select_related("producto", "insumo")
        gestionables = sedes_que_gestiona(request.user)
        if gestionables is not None:
            alertas = alertas.filter(sede_id__in=gestionables)

        sede = request.query_params.get("sede")
        if sede not in (None, ""):
            try:
                alertas = alertas.filter(sede_id=int(sede))
            except ValueError:
                raise ValidationError({"sede": "La sede debe ser un id numérico."})

        if estado != "todas":
            alertas = alertas.filter(estado=estado)
        if estado == "resuelta":
            alertas = alertas.order_by("-resuelta_en", "-id")[:50]

        alertas = list(alertas)
        return Response([datos_alerta(alerta) for alerta in alertas])
