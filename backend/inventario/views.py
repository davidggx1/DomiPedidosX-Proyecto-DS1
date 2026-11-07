"""HU-14 · API de existencias. Los listados y cambios quedan acotados a la sede del usuario."""
from drf_spectacular.utils import OpenApiParameter, extend_schema, extend_schema_view
from rest_framework import viewsets
from rest_framework.exceptions import PermissionDenied, ValidationError

from menu.disponibilidad import sedes_que_gestiona
from menu.permissions import EsPersonalDeMenu

from .models import InventarioInsumo, InventarioProducto
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
