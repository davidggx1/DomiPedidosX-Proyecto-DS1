from django.urls import re_path

from .consumers import EstadoPedidoConsumer

websocket_urlpatterns = [
    re_path(r'ws/pedidos/(?P<pedido_id>[0-9]+)/estado/$', EstadoPedidoConsumer.as_asgi()),
]
