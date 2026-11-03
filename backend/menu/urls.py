from django.urls import include, path
from rest_framework.routers import SimpleRouter

from .views import (
    AdicionViewSet,
    CategoriaMenuViewSet,
    InsumoViewSet,
    ProductoAdicionViewSet,
    ProductoImagenView,
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

urlpatterns = [
    path("productos/<int:pk>/imagen/", ProductoImagenView.as_view(), name="producto-imagen"),
    path("productos-opciones/", ProductoOpcionesView.as_view(), name="producto-opciones"),
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
    path("", include(router.urls)),
]
