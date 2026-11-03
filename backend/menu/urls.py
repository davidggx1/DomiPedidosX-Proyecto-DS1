from django.urls import include, path
from rest_framework.routers import SimpleRouter

from .views import CategoriaMenuViewSet, ProductoImagenView

router = SimpleRouter()
router.register("categorias", CategoriaMenuViewSet, basename="categoria")

urlpatterns = [
    path("productos/<int:pk>/imagen/", ProductoImagenView.as_view(), name="producto-imagen"),
    path("", include(router.urls)),
]
