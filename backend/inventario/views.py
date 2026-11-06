from drf_spectacular.utils import OpenApiParameter, extend_schema, extend_schema_view
from rest_framework import viewsets
from rest_framework.exceptions import ValidationError

from menu.disponibilidad import sedes_que_gestiona
from menu.permissions import EsPersonalDeMenu

from .models import InventarioInsumo, InventarioProducto
from .serializers import InventarioInsumoSerializer, InventarioProductoSerializer

PARAMETRO_SEDE = OpenApiParameter(
    "sede", int, description="Filtra por sede (el operador solo ve la suya)"
)


class InventarioBaseViewSet(viewsets.ModelViewSet):
    """Stock per sede. The operador only reaches the records of its own sede"""

    permission_classes = [EsPersonalDeMenu]
    modelo = None
    relaciones = ()
    orden = ()

    def get_queryset(self):
        existencias = self.modelo.objects.select_related(*self.relaciones).order_by(*self.orden)
        gestionables = sedes_que_gestiona(self.request.user)
        if gestionables is not None:
            # a record of another sede answers 404, like it did not exist
            existencias = existencias.filter(sede_id__in=gestionables)

        sede = self.request.query_params.get("sede")
        if self.action == "list" and sede:
            if not sede.isdigit():
                raise ValidationError({"sede": "La sede debe ser un id numérico."})
            existencias = existencias.filter(sede_id=int(sede))
        return existencias


@extend_schema_view(list=extend_schema(parameters=[PARAMETRO_SEDE]))
class InventarioProductoViewSet(InventarioBaseViewSet):
    """HU-14: existencias de productos por sede (crear, ver, ajustar y quitar)"""

    serializer_class = InventarioProductoSerializer
    modelo = InventarioProducto
    relaciones = ("sede", "producto", "producto__categoria")
    orden = ("sede__nombre", "producto__nombre")


@extend_schema_view(list=extend_schema(parameters=[PARAMETRO_SEDE]))
class InventarioInsumoViewSet(InventarioBaseViewSet):
    """HU-14: existencias de ingredientes por sede (crear, ver, ajustar y quitar)"""

    serializer_class = InventarioInsumoSerializer
    modelo = InventarioInsumo
    relaciones = ("sede", "insumo")
    orden = ("sede__nombre", "insumo__nombre")
