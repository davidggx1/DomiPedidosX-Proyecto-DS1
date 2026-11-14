from django.urls import re_path
from django.urls import path
from .consumers import EstadoPedidoConsumer
from .consumers import EstadoRepartidoresConsumer, MisEntregasConsumer, PedidosEntrantesConsumer

websocket_urlpatterns = [
    re_path(
        r"ws/pedidos/(?P<pedido_id>[0-9]+)/estado/$",
        EstadoPedidoConsumer.as_asgi(),
    ),
    path(
        "ws/pedidos/entrantes/",
        PedidosEntrantesConsumer.as_asgi(),
    ),
    path(
        "ws/pedidos/mis-entregas/",
        MisEntregasConsumer.as_asgi(),
    ),
    path(
        "ws/pedidos/repartidores/",
        EstadoRepartidoresConsumer.as_asgi(),
    ),
]

