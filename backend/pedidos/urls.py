from django.urls import path

from .views import ComandaCocinaView, EstadoPedidoView, TableroCocinaView

urlpatterns = [
    path("<int:pk>/estado/", EstadoPedidoView.as_view(), name="pedido-estado"),
    path("<int:pk>/cocina/", ComandaCocinaView.as_view(), name="pedido-comanda"),
    path("cocina/tablero/", TableroCocinaView.as_view(), name="cocina-tablero"),
]
