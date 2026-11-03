from django.urls import path

from .views import ProductoImagenView

urlpatterns = [
    path("productos/<int:pk>/imagen/", ProductoImagenView.as_view(), name="producto-imagen"),
]
