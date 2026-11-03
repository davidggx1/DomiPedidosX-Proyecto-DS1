from django.db.models import Count
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiParameter, extend_schema, extend_schema_view
from rest_framework import generics, mixins, permissions, status, viewsets
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response

from .models import Adicion, CategoriaMenu, Insumo, Producto, ProductoAdicion
from .permissions import EsPersonalDeMenu
from .serializers import (
    AdicionSerializer,
    CategoriaMenuSerializer,
    InsumoOpcionSerializer,
    ProductoAdicionSerializer,
    ProductoImagenSerializer,
    ProductoOpcionSerializer,
)


class ProductoImagenView(generics.GenericAPIView):
    """Uploads, replaces or deletes the product image (admin only)"""

    queryset = Producto.objects.all()
    serializer_class = ProductoImagenSerializer
    parser_classes = [MultiPartParser, FormParser]
    permission_classes = [permissions.IsAdminUser]

    def post(self, request, *args, **kwargs):
        producto = self.get_object()
        imagen_anterior = producto.imagen.name

        serializer = self.get_serializer(producto, data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        # When replacing the image, the old file is deleted from storage
        if imagen_anterior and imagen_anterior != producto.imagen.name:
            producto.imagen.storage.delete(imagen_anterior)

        return Response(serializer.data, status=status.HTTP_200_OK)

    def delete(self, request, *args, **kwargs):
        producto = self.get_object()
        if producto.imagen:
            producto.imagen.delete(save=True)
        return Response(status=status.HTTP_204_NO_CONTENT)


class CategoriaMenuViewSet(
    mixins.CreateModelMixin,
    mixins.UpdateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    """Lists, creates and edits menu categories (no delete on purpose)"""

    serializer_class = CategoriaMenuSerializer
    permission_classes = [EsPersonalDeMenu]

    def get_queryset(self):
        return CategoriaMenu.objects.annotate(
            total_productos=Count("productos")
        ).order_by("nombre")


@extend_schema_view(
    list=extend_schema(
        parameters=[
            OpenApiParameter(
                "activa",
                bool,
                description="true: solo activas · false: solo eliminadas · sin valor: todas.",
            )
        ]
    )
)
class AdicionViewSet(viewsets.ModelViewSet):
    """HU-76: registrar, editar y eliminar (borrado lógico) adiciones."""

    serializer_class = AdicionSerializer
    permission_classes = [EsPersonalDeMenu]

    def get_queryset(self):
        adiciones = Adicion.objects.select_related("insumo").order_by("nombre")
        activa = self.request.query_params.get("activa")
        if activa is not None:
            adiciones = adiciones.filter(activa=activa.lower() in ("true", "1"))
        return adiciones

    def perform_destroy(self, instance):
        # Borrado lógico: la adición deja de ofrecerse, pero los pedidos
        # anteriores la siguen referenciando con su precio original.
        instance.activa = False
        instance.save(update_fields=["activa"])


class InsumoViewSet(viewsets.ReadOnlyModelViewSet):
    """Insumos activos, para elegir cuál consume una adición. HU-77 agrega su gestión."""

    serializer_class = InsumoOpcionSerializer
    permission_classes = [EsPersonalDeMenu]
    queryset = Insumo.objects.filter(activo=True).order_by("nombre")


class ProductoOpcionesView(generics.ListAPIView):
    """Lista corta de productos activos (id y nombre) para los selectores de gestión."""

    serializer_class = ProductoOpcionSerializer
    permission_classes = [EsPersonalDeMenu]
    queryset = Producto.objects.filter(activo=True).select_related("categoria").order_by("nombre")
    pagination_class = None


class ProductoAdicionViewSet(viewsets.ModelViewSet):
    """
    Adiciones que ofrece un producto: /api/menu/productos/<id>/adiciones/.

    Quitar una adición de un producto borra solo el vínculo. Los pedidos guardan
    la adición (no el vínculo), así que el historial no se ve afectado.
    """

    serializer_class = ProductoAdicionSerializer
    permission_classes = [EsPersonalDeMenu]

    def get_producto(self):
        return get_object_or_404(Producto, pk=self.kwargs["producto_pk"])

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return ProductoAdicion.objects.none()
        return (
            ProductoAdicion.objects.filter(producto=self.get_producto())
            .select_related("adicion")
            .order_by("adicion__nombre")
        )

    def get_serializer_context(self):
        contexto = super().get_serializer_context()
        if "producto_pk" in self.kwargs:
            contexto["producto"] = self.get_producto()
        return contexto

    def perform_create(self, serializer):
        serializer.save(producto=self.get_producto())
