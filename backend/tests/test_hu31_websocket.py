import pytest
from channels.testing import WebsocketCommunicator
from django.contrib.auth.models import Group
from django.test import override_settings

from config.asgi import application
from pedidos.models import EstadoPedido, Pedido
from sedes.models import Ciudad, Sede
from usuarios.models import Empleado, Usuario
from usuarios.roles import COCINA

pytestmark = pytest.mark.django_db(transaction=True)


@pytest.mark.asyncio
@override_settings(
    CHANNEL_LAYERS={'default': {'BACKEND': 'channels.layers.InMemoryChannelLayer'}}
)
async def test_websocket_rechaza_usuario_no_autenticado():
    communicator = WebsocketCommunicator(application, '/ws/pedidos/1/estado/')
    connected, _ = await communicator.connect()
    assert not connected
    await communicator.disconnect()
