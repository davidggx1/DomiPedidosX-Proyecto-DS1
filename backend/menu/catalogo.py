"""
HU-18 · Menú del cliente por sede y categoría.

Vive en un módulo aparte de views.py y serializers.py porque esos archivos
reciben a la vez los cambios de gestión del menú (HU-11, HU-13, HU-75...).
Así se evitan conflictos entre ramas.
"""
from decimal import Decimal
import unicodedata

from django.db.models import Prefetch
from django.shortcuts import get_object_or_404
from django.db import connection
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




def producto_disponible(producto, inventario, inventarios_insumos=None):
    """Return whether a product can be ordered with the current stock."""
    if inventario is None or not inventario.disponible:
        return False
    if producto.tipo_control_stock == Producto.TipoControlStock.PRODUCTO:
        return inventario.stock_actual > 0
    if producto.tipo_control_stock == Producto.TipoControlStock.INSUMOS:
        inventarios_insumos = inventarios_insumos or {}
        for receta in producto.insumos_requeridos.all():
            stock = inventarios_insumos.get(receta.insumo_id)
            if stock is None or not stock.disponible:
                return False
            if stock.stock_actual < Decimal(receta.cantidad_necesaria):
                return False
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
        inventarios_insumos = self.context.get("inventarios_insumos", {})
        return producto_disponible(producto, inventario, inventarios_insumos)


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


def _normalizar_texto(texto: str) -> str:
    """Elimina tildes/diacríticos y pasa a minúsculas para comparación insensible."""
    nfkd = unicodedata.normalize("NFKD", texto)
    sin_tildes = "".join(c for c in nfkd if not unicodedata.combining(c))
    return sin_tildes.casefold()


def _soporta_unaccent() -> bool:
    """Verifica si PostgreSQL tiene habilitada la extensión unaccent."""
    if connection.vendor != "postgresql":
        return False
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1 FROM pg_extension WHERE extname = 'unaccent';")
            return cursor.fetchone() is not None
    except Exception:
        return False


class MenuSedeView(APIView):
    """
    GET /api/menu/sedes/<id>/menu/

    Menú de una sede activa: categorías activas con sus productos activos y si
    cada uno se puede pedir en esa sede. Soporta filtro por `?categoria=<id>` y
    búsqueda insensible a mayúsculas y tildes mediante `?q=<texto>` (HU-19).
    """

    permission_classes = [AllowAny]
    authentication_classes = []

    @extend_schema(
        parameters=[
            OpenApiParameter(
                "categoria",
                int,
                description="Id de una categoría para devolver solo esa.",
            ),
            OpenApiParameter(
                "q",
                str,
                description="Texto a buscar en el nombre del producto (ignora mayúsculas y tildes).",
            ),
        ],
        responses=MenuSedeSerializer,
    )
    def get(self, request, sede_pk):
        sede = get_object_or_404(Sede, pk=sede_pk, activa=True)

        busqueda = (request.query_params.get("q") or "").strip()
        usar_unaccent_sql = bool(busqueda) and _soporta_unaccent()

        productos_qs = Producto.objects.filter(activo=True).order_by("nombre")
        if busqueda and usar_unaccent_sql:
            productos_qs = productos_qs.filter(nombre__unaccent__icontains=busqueda)

        categorias = (
            CategoriaMenu.objects.filter(activa=True)
            .order_by("nombre")
            .prefetch_related(
                Prefetch(
                    "productos",
                    queryset=productos_qs,
                    to_attr="productos_activos",
                )
            )
        )

        categoria = request.query_params.get("categoria")
        if categoria is not None:
            if not categoria.isdigit():
                raise ValidationError({"categoria": "Debe ser el id numérico de una categoría."})
            categorias = categorias.filter(pk=int(categoria))

        categorias_lista = list(categorias)

        # Fallback en Python si PostgreSQL aún no tiene instalada la extensión unaccent
        if busqueda and not usar_unaccent_sql:
            termino = _normalizar_texto(busqueda)
            for cat in categorias_lista:
                cat.productos_activos = [
                    p for p in cat.productos_activos if termino in _normalizar_texto(p.nombre)
                ]

        inventarios = {
            inventario.producto_id: inventario
            for inventario in InventarioProducto.objects.filter(sede=sede)
        }
        from inventario.models import InventarioInsumo

        inventarios_insumos = {
            inventario.insumo_id: inventario
            for inventario in InventarioInsumo.objects.filter(sede=sede)
        }

        serializer = MenuSedeSerializer(
            {"sede": sede, "categorias": categorias_lista},
            context={
                "request": request,
                "inventarios": inventarios,
                "inventarios_insumos": inventarios_insumos,
            },
        )
        return Response(serializer.data)