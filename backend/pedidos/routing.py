from django.urls import re_path

from .consumers import EstadoPedidoConsumer

websocket_urlpatterns = [
    re_path(r'ws/pedidos/(?P<pedido_id>[0-9]+)/estado/$', EstadoPedidoConsumer.as_asgi()),
from django.urls import path
from .consumers import EstadoPedidoConsumer
from .consumers import PedidosEntrantesConsumer

websocket_urlpatterns = [
    re_path(r'ws/pedidos/(?P<pedido_id>[0-9]+)/estado/$', EstadoPedidoConsumer.as_asgi()),
     path("ws/pedidos/entrantes/", PedidosEntrantesConsumer.as_asgi()),
]
