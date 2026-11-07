from django.urls import path

from .views import (
    AsignacionRepartidorView,
    ComandaCocinaView,
    DespachoView,
    EstadoPedidoView,
    TableroCocinaView,
    PedidosEntrantesView,
    ConfirmarPedidoView,
    AprobarPedidoView, CrearPedidoOperadorView,
)
from .entregas import DetalleEntregaView, MisEntregasView
from .resumen import ResumenDiaView

urlpatterns = [
    path("<int:pk>/estado/", EstadoPedidoView.as_view(), name="pedido-estado"),
    path("<int:pk>/cocina/", ComandaCocinaView.as_view(), name="pedido-comanda"),
    path("cocina/tablero/", TableroCocinaView.as_view(), name="cocina-tablero"),
    path("<int:pk>/repartidor/", AsignacionRepartidorView.as_view(), name="pedido-repartidor"),
    path("despacho/", DespachoView.as_view(), name="despacho"),
    path("entrantes/", PedidosEntrantesView.as_view(), name="pedidos-entrantes"),
    path("confirmar/", ConfirmarPedidoView.as_view(), name="pedidos-confirmar"),
    path("<int:pk>/aprobar/", AprobarPedidoView.as_view(), name="pedidos-aprobar"),
    path("operador/crear/", CrearPedidoOperadorView.as_view(), name="pedidos-operador-crear"),
    path("mis-entregas/", MisEntregasView.as_view(), name="mis-entregas"),
    path("mis-entregas/<int:pk>/", DetalleEntregaView.as_view(), name="mis-entregas-detalle"),
    path("resumen-dia/", ResumenDiaView.as_view(), name="resumen-dia"),
]
