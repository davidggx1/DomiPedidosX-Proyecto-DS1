import time

import pytest
from asgiref.sync import sync_to_async
from channels.testing import WebsocketCommunicator
from django.contrib.auth.models import Group
from rest_framework_simplejwt.tokens import AccessToken

from config.asgi import application
from pedidos.eventos import notificar_pedido
from pedidos.models import EstadoPedido, Pedido
from sedes.models import Ciudad, Sede
from usuarios.models import Empleado, Usuario

pytestmark = [pytest.mark.asyncio, pytest.mark.django_db(transaction=True)]


def _sede(nombre):
    ciudad, _ = Ciudad.objects.get_or_create(nombre="Cali")
    return Sede.objects.create(
        ciudad=ciudad, nombre=nombre, direccion="Calle 1 # 2-3", latitud=3.45,
        longitud=-76.53, barrio="Granada", telefono="3000000000", correo="s@correo.com",
    )


def _personal(rol, email, sede=None):
    usuario = Usuario.objects.create_user(username=email, email=email, password="ClaveSegura2026")
    usuario.groups.add(Group.objects.get_or_create(name=rol)[0])
    if sede:
        Empleado.objects.create(
            usuario=usuario, sede=sede, tipo_documento="CC", num_documento=email[:10],
            nombres="N", apellidos="A", celular="3001234567", direccion="Calle 4",
        )
    return usuario


def _pedido(sede, numero):
    return Pedido.objects.create(
        numero_pedido=numero, sede=sede, estado=EstadoPedido.PENDIENTE_APROBACION
    )


def _canal(usuario):
    token = str(AccessToken.for_user(usuario))
    return WebsocketCommunicator(application, f"/ws/pedidos/entrantes/?token={token}")


async def test_operador_recibe_en_menos_de_10s_el_pedido_de_su_sede():
    sede = await sync_to_async(_sede)("Norte")
    operador = await sync_to_async(_personal)("operador", "op_norte@correo.com", sede)
    canal = _canal(operador)
    conectado, _ = await canal.connect()
    assert conectado

    pedido = await sync_to_async(_pedido)(sede, "P-1")
    inicio = time.monotonic()
    await sync_to_async(notificar_pedido)(pedido)
    data = await canal.receive_json_from(timeout=10)

    assert time.monotonic() - inicio < 10
    assert data["tipo"] == "pedido_nuevo"
    assert data["pedido"]["numero_pedido"] == "P-1"
    await canal.disconnect()


async def test_sedes_no_se_mezclan_en_paralelo():
    norte = await sync_to_async(_sede)("Norte")
    sur = await sync_to_async(_sede)("Sur")
    op_norte = await sync_to_async(_personal)("operador", "op_norte@correo.com", norte)
    op_sur = await sync_to_async(_personal)("operador", "op_sur@correo.com", sur)
    canal_norte, canal_sur = _canal(op_norte), _canal(op_sur)
    assert (await canal_norte.connect())[0]
    assert (await canal_sur.connect())[0]

    p_norte = await sync_to_async(_pedido)(norte, "P-N")
    p_sur = await sync_to_async(_pedido)(sur, "P-S")
    await sync_to_async(notificar_pedido)(p_norte)
    await sync_to_async(notificar_pedido)(p_sur)

    assert (await canal_norte.receive_json_from(timeout=5))["pedido"]["numero_pedido"] == "P-N"
    assert (await canal_sur.receive_json_from(timeout=5))["pedido"]["numero_pedido"] == "P-S"
    assert await canal_norte.receive_nothing(timeout=0.5)
    assert await canal_sur.receive_nothing(timeout=0.5)
    await canal_norte.disconnect()
    await canal_sur.disconnect()


async def test_administrador_recibe_pedidos_de_cualquier_sede():
    sede = await sync_to_async(_sede)("Norte")
    admin = await sync_to_async(_personal)("administrador", "admin@correo.com")
    canal = _canal(admin)
    assert (await canal.connect())[0]

    pedido = await sync_to_async(_pedido)(sede, "P-1")
    await sync_to_async(notificar_pedido)(pedido)
    assert (await canal.receive_json_from(timeout=5))["pedido"]["numero_pedido"] == "P-1"
    await canal.disconnect()


async def test_sin_token_o_token_invalido_es_rechazado():
    sin_token = WebsocketCommunicator(application, "/ws/pedidos/entrantes/")
    assert (await sin_token.connect())[0] is False
    malo = WebsocketCommunicator(application, "/ws/pedidos/entrantes/?token=basura")
    assert (await malo.connect())[0] is False


async def test_roles_sin_permiso_o_sin_sede_son_rechazados():
    sede = await sync_to_async(_sede)("Norte")
    cocina = await sync_to_async(_personal)("cocina", "cocina@correo.com", sede)
    cliente = await sync_to_async(
        lambda: Usuario.objects.create_user(
            username="c@correo.com", email="c@correo.com", password="ClaveSegura2026"
        )
    )()
    operador_sin_sede = await sync_to_async(_personal)("operador", "sinsede@correo.com")

    for usuario in (cocina, cliente, operador_sin_sede):
        assert (await _canal(usuario).connect())[0] is False