from django.urls import include, path
from rest_framework.routers import SimpleRouter

from menu.agotados import AgotadosPendientesView

from .views import (
    AlertasInventarioView,
    InventarioInsumoViewSet,
    InventarioProductoViewSet,
)

router = SimpleRouter()
router.register("productos", InventarioProductoViewSet, basename="inventario-producto")
router.register("insumos", InventarioInsumoViewSet, basename="inventario-insumo")

urlpatterns = [
    path("alertas/", AlertasInventarioView.as_view(), name="inventario-alertas"),
    path("agotados/", AgotadosPendientesView.as_view(), name="inventario-agotados"),  # HU-17
    path("", include(router.urls)),
]
