from django.urls import path

from .views import EstadoPedidoView

urlpatterns = [
    path("<int:pk>/estado/", EstadoPedidoView.as_view(), name="pedido-estado"),
]
