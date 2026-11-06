from django.urls import include, path
from rest_framework.routers import SimpleRouter

from .views import InventarioInsumoViewSet, InventarioProductoViewSet

router = SimpleRouter()
router.register("productos", InventarioProductoViewSet, basename="inventario-producto")
router.register("insumos", InventarioInsumoViewSet, basename="inventario-insumo")

urlpatterns = [path("", include(router.urls))]
