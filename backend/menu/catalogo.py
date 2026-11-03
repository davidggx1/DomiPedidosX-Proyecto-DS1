"""
HU-18 · Menú del cliente por sede y categoría.

Vive en un módulo aparte de views.py y serializers.py porque esos archivos
reciben a la vez los cambios de gestión del menú (HU-11, HU-13, HU-75...).
Así se evitan conflictos entre ramas.
"""
from django.db.models import Prefetch
from django.shortcuts import get_object_or_404
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema, extend_schema_field
from rest_framework import generics, serializers
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from inventario.models import InventarioProducto
from sedes.models import Sede

from .models import CategoriaMenu, Producto


def producto_disponible(producto, inventario):
    """
    Un producto se puede pedir en una sede si:
    - la sede lo tiene en su inventario y marcado como disponible (HU-13), y
    - cuando se controla por unidades, todavía le queda stock.
    El control por insumos (HU-14) llega en el Sprint 2.
    """
    if inventario is None or not inventario.disponible:
        return False
    if producto.tipo_control_stock == Producto.TipoControlStock.PRODUCTO:
        return inventario.stock_actual > 0
    return True


class ProductoMenuSerializer(serializers.ModelSerializer):
    precio = serializers.DecimalField(
        source="precio_base", max_digits=10, decimal_places=2, read_only=True
    )
    imagen = serializers.SerializerMethodField()
    disponible = serializers.SerializerMethodField()

    class Meta:
        model = Producto
        fields = ["id", "nombre", "descripcion", "precio", "imagen", "disponible"]

    @extend_schema_field(OpenApiTypes.URI)
    def get_imagen(self, producto):
        if producto.imagen:
            request = self.context.get("request")
            url = producto.imagen.url
            return request.build_absolute_uri(url) if request else url
        return producto.imagen_url or None

    @extend_schema_field(OpenApiTypes.BOOL)
    def get_disponible(self, producto):
        inventario = self.context["inventarios"].get(producto.id)
        return producto_disponible(producto, inventario)


class CategoriaConProductosSerializer(serializers.ModelSerializer):
    productos = ProductoMenuSerializer(source="productos_activos", many=True, read_only=True)

    class Meta:
        model = CategoriaMenu
        fields = ["id", "nombre", "descripcion", "productos"]


class SedeResumenSerializer(serializers.ModelSerializer):
    class Meta:
        model = Sede
        fields = ["id", "nombre", "direccion", "barrio"]


class MenuSedeSerializer(serializers.Serializer):
    sede = SedeResumenSerializer()
    categorias = CategoriaConProductosSerializer(many=True)


class SedesMenuView(generics.ListAPIView):
    """GET /api/menu/sedes/ · Sedes activas que el cliente puede elegir para ver el menú."""

    serializer_class = SedeResumenSerializer
    permission_classes = [AllowAny]
    authentication_classes = []
    pagination_class = None
    queryset = Sede.objects.filter(activa=True).order_by("nombre")


class MenuSedeView(APIView):
    """
    GET /api/menu/sedes/<id>/menu/

    Menú de una sede activa: categorías activas con sus productos activos y si
    cada uno se puede pedir en esa sede. Las categorías sin productos también se
    devuelven, para que el cliente vea que están vacías.
    Es público: no exige sesión, y así un token vencido no bloquea el menú.
    """

    permission_classes = [AllowAny]
    authentication_classes = []

    @extend_schema(
        parameters=[
            OpenApiParameter(
                "categoria",
                int,
                description="Id de una categoría para devolver solo esa.",
            )
        ],
        responses=MenuSedeSerializer,
    )
    def get(self, request, sede_pk):
        sede = get_object_or_404(Sede, pk=sede_pk, activa=True)

        categorias = (
            CategoriaMenu.objects.filter(activa=True)
            .order_by("nombre")
            .prefetch_related(
                Prefetch(
                    "productos",
                    queryset=Producto.objects.filter(activo=True).order_by("nombre"),
                    to_attr="productos_activos",
                )
            )
        )

        categoria = request.query_params.get("categoria")
        if categoria is not None:
            if not categoria.isdigit():
                raise ValidationError({"categoria": "Debe ser el id numérico de una categoría."})
            categorias = categorias.filter(pk=int(categoria))

        inventarios = {
            inventario.producto_id: inventario
            for inventario in InventarioProducto.objects.filter(sede=sede)
        }

        serializer = MenuSedeSerializer(
            {"sede": sede, "categorias": categorias},
            context={"request": request, "inventarios": inventarios},
        )
        return Response(serializer.data)
