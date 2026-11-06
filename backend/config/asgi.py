import os

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

from django.core.asgi import get_asgi_application

# Inicializa Django antes de importar rutas que dependen de modelos.
django_application = get_asgi_application()

from channels.auth import AuthMiddlewareStack
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.routing import ProtocolTypeRouter, URLRouter
from pedidos.middleware import JWTAuthMiddleware
from pedidos.routing import websocket_urlpatterns

application = ProtocolTypeRouter({
    'http': django_application,
    'websocket': AuthMiddlewareStack(URLRouter(websocket_urlpatterns)),
    'websocket': JWTAuthMiddleware(URLRouter(websocket_urlpatterns)),
})
