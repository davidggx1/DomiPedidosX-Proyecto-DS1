from django.urls import include, path
from rest_framework.routers import SimpleRouter
from .catalogo import MenuSedeView, SedesMenuView

from .views import (
    AdicionViewSet,
    CategoriaMenuViewSet,
    InsumoViewSet,
    ProductoAdicionViewSet,
    ProductoImagenView,
    ProductoInsumoViewSet,
    ProductoOpcionesView,
)

router = SimpleRouter()
router.register("categorias", CategoriaMenuViewSet, basename="categoria")
router.register("adiciones", AdicionViewSet, basename="adicion")
router.register("insumos", InsumoViewSet, basename="insumo")

producto_adiciones = ProductoAdicionViewSet.as_view({"get": "list", "post": "create"})
producto_adicion_detalle = ProductoAdicionViewSet.as_view(
    {"get": "retrieve", "patch": "partial_update", "delete": "destroy"}
)
producto_ingredientes = ProductoInsumoViewSet.as_view({"get": "list", "post": "create"})
producto_ingrediente_detalle = ProductoInsumoViewSet.as_view(
    {"get": "retrieve", "patch": "partial_update", "delete": "destroy"}
)

urlpatterns = [
    path("productos/<int:pk>/imagen/", ProductoImagenView.as_view(), name="producto-imagen"),
    path("productos-opciones/", ProductoOpcionesView.as_view(), name="producto-opciones"),
    path("sedes/", SedesMenuView.as_view(), name="menu-sedes"),
    path("sedes/<int:sede_pk>/menu/", MenuSedeView.as_view(), name="menu-sede"),
    path(
        "productos/<int:producto_pk>/adiciones/",
        producto_adiciones,
        name="producto-adiciones",
    ),
    path(
        "productos/<int:producto_pk>/adiciones/<int:pk>/",
        producto_adicion_detalle,
        name="producto-adicion-detalle",
    ),
    path(
        "productos/<int:producto_pk>/ingredientes/",
        producto_ingredientes,
        name="producto-ingredientes",
    ),
    path(
        "productos/<int:producto_pk>/ingredientes/<int:pk>/",
        producto_ingrediente_detalle,
        name="producto-ingrediente-detalle",
    ),
    path("", include(router.urls)),
]
