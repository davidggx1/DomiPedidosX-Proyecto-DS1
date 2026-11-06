from django.urls import path

from .consumers import TableroCocinaConsumer

websocket_urlpatterns = [
    path("ws/pedidos/cocina/", TableroCocinaConsumer.as_asgi()),
]
