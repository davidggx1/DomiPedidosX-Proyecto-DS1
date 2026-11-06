"""Pruebas del canal WebSocket del tablero de cocina (HU-29)."""
from urllib.parse import quote

import pytest
from asgiref.sync import async_to_sync, sync_to_async
from channels.testing import WebsocketCommunicator
from django.contrib.auth.models import Group
from rest_framework_simplejwt.tokens import AccessToken

from pedidos.consumers import TableroCocinaConsumer
from pedidos.estados import cambiar_estado
from pedidos.models import EstadoPedido, Pedido
from sedes.models import Ciudad, Sede
from usuarios.models import Empleado, Usuario
from usuarios.roles import COCINA

pytestmark = pytest.mark.django_db(transaction=True)


def crear_usuario_cocina():
    ciudad = Ciudad.objects.create(nombre="Cali")
    sede = Sede.objects.create(
        ciudad=ciudad,
        nombre="Sede WebSocket",
        direccion="Calle 1 # 2-3",
        latitud=3.45,
        longitud=-76.53,
        barrio="Centro",
        telefono="3000000000",
        correo="sede-ws@correo.com",
    )
    usuario = Usuario.objects.create_user(
        username="cocina-ws", email="cocina-ws@correo.com", password="ClaveSegura2026"
    )
    usuario.groups.add(Group.objects.get_or_create(name=COCINA)[0])
    Empleado.objects.create(
        usuario=usuario,
        sede=sede,
        tipo_documento="CC",
        num_documento="1234567890",
        nombres="Cocina",
        apellidos="Prueba",
        celular="3001234567",
        direccion="Calle 4",
    )
    return usuario, sede


def test_cocina_recibe_eventos_de_su_sede():
    usuario, sede = crear_usuario_cocina()
    token = str(AccessToken.for_user(usuario))

    pedido = Pedido.objects.create(numero_pedido="WS-42", sede=sede)

    async def ejecutar():
        communicator = WebsocketCommunicator(
            TableroCocinaConsumer.as_asgi(),
            f"/ws/pedidos/cocina/?token={quote(token)}",
        )
        conectado, _ = await communicator.connect()
        assert conectado is True
        assert await communicator.receive_json_from() == {"tipo": "conexion.establecida"}

        # El cambio real pasa por la máquina de estados y su señal debe
        # publicar automáticamente el evento en el grupo de esta sede.
        await sync_to_async(cambiar_estado)(
            pedido, EstadoPedido.EN_PREPARACION, usuario, COCINA
        )
        mensaje = await communicator.receive_json_from()
        assert mensaje == {
            "tipo": "pedido.actualizado",
            "pedido_id": pedido.pk,
            "sede_id": sede.pk,
            "estado": EstadoPedido.EN_PREPARACION,
            "estado_anterior": EstadoPedido.RECIBIDO,
        }
        await communicator.disconnect()

    async_to_sync(ejecutar)()
