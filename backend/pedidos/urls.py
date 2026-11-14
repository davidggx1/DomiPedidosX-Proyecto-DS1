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
from .cancelacion import CancelarPedidoView
from .capacidad import EstadoCapacidadView
from .entregas import ActualizarEntregaView, DetalleEntregaView, MisEntregasView
from .historial import FichaPedidoView, HistorialPedidosView
from .indicadores import IndicadoresDiaView
from .reportes_tiempos import ReporteTiemposView
from .resumen import ResumenDiaView
from .seguimiento import MisPedidosView

urlpatterns = [
    path("<int:pk>/estado/", EstadoPedidoView.as_view(), name="pedido-estado"),
    path("<int:pk>/cancelar/", CancelarPedidoView.as_view(), name="pedido-cancelar"),
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
    path("mis-entregas/<int:pk>/entrega/", ActualizarEntregaView.as_view(), name="mis-entregas-actualizar"),
    path("capacidad/", EstadoCapacidadView.as_view(), name="pedidos-capacidad"),
    path("resumen-dia/", ResumenDiaView.as_view(), name="resumen-dia"),
    path("indicadores/", IndicadoresDiaView.as_view(), name="indicadores-dia"),
    path("reportes/tiempos/", ReporteTiemposView.as_view(), name="reporte-tiempos"),  # HU-72
    path("historial/", HistorialPedidosView.as_view(), name="historial-pedidos"),
    path("historial/<int:pk>/", FichaPedidoView.as_view(), name="ficha-pedido"),
    path("mios/", MisPedidosView.as_view(), name="mis-pedidos"),
]