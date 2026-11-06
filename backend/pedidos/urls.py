from django.urls import path

from .views import (
    AsignacionRepartidorView,
    ComandaCocinaView,
    DespachoView,
    EstadoPedidoView,
    TableroCocinaView,
    PedidosEntrantesView,
)

urlpatterns = [
    path("<int:pk>/estado/", EstadoPedidoView.as_view(), name="pedido-estado"),
    path("<int:pk>/cocina/", ComandaCocinaView.as_view(), name="pedido-comanda"),
    path("cocina/tablero/", TableroCocinaView.as_view(), name="cocina-tablero"),
    path("<int:pk>/repartidor/", AsignacionRepartidorView.as_view(), name="pedido-repartidor"),
    path("despacho/", DespachoView.as_view(), name="despacho"),
    path("entrantes/", PedidosEntrantesView.as_view(), name="pedidos-entrantes"),
]
