"""Pruebas de HU-42 · Lista de pedidos asignados en tiempo real (WebSocket del repartidor)."""
import time

import pytest
from asgiref.sync import sync_to_async
from channels.testing import WebsocketCommunicator
from django.contrib.auth.models import Group
from rest_framework_simplejwt.tokens import AccessToken

from config.asgi import application
from pedidos.asignacion import asignar, retirar
from pedidos.estados import cambiar_estado
from pedidos.models import EstadoPedido as E
from pedidos.models import Pedido
from sedes.models import Ciudad, Sede
from usuarios.models import Empleado, Repartidor, Usuario
from usuarios.roles import OPERADOR, REPARTIDOR

pytestmark = [pytest.mark.asyncio, pytest.mark.django_db(transaction=True)]

RUTA = "/ws/pedidos/mis-entregas/"


def _sede():
    ciudad, _ = Ciudad.objects.get_or_create(nombre="Cali")
    return Sede.objects.create(
        ciudad=ciudad, nombre="Centro", direccion="Calle 1 # 2-3", latitud=3.45,
        longitud=-76.53, barrio="Granada", telefono="3000000000", correo="s@correo.com",
    )


def _personal(rol, email, sede):
    usuario = Usuario.objects.create_user(username=email, email=email, password="ClaveSegura2026")
    usuario.groups.add(Group.objects.get_or_create(name=rol)[0])
    empleado = Empleado.objects.create(
        usuario=usuario, sede=sede, tipo_documento="CC", num_documento=email[:10],
        nombres="N", apellidos="A", celular="3001234567", direccion="Calle 4",
    )
    return usuario, empleado


def _repartidor(email, sede):
    usuario, empleado = _personal(REPARTIDOR, email, sede)
    return usuario, Repartidor.objects.create(empleado=empleado, disponible=True)


def _pedido(sede, numero="P-1"):
    return Pedido.objects.create(numero_pedido=numero, sede=sede, estado=E.LISTO_DESPACHO)


def _canal(usuario):
    token = str(AccessToken.for_user(usuario))
    return WebsocketCommunicator(application, f"{RUTA}?token={token}")


async def _conectar(usuario):
    canal = _canal(usuario)
    conectado, _ = await canal.connect()
    assert conectado
    return canal


# --- Criterio 2: la lista se actualiza en tiempo real --------------------------


async def test_repartidor_recibe_en_menos_de_10s_el_pedido_que_le_asignan():
    sede = await sync_to_async(_sede)()
    usuario, ana = await sync_to_async(_repartidor)("ana@correo.com", sede)
    pedido = await sync_to_async(_pedido)(sede)
    canal = await _conectar(usuario)

    inicio = time.monotonic()
    await sync_to_async(asignar)(pedido, ana)
    data = await canal.receive_json_from(timeout=10)

    assert time.monotonic() - inicio < 10
    assert data["tipo"] == "entregas_actualizadas"
    assert data["pedido_id"] == pedido.id
    await canal.disconnect()


async def test_al_retirar_la_asignacion_se_avisa_al_repartidor_que_la_tenia():
    sede = await sync_to_async(_sede)()
    usuario, ana = await sync_to_async(_repartidor)("ana@correo.com", sede)
    pedido = await sync_to_async(_pedido)(sede)
    await sync_to_async(asignar)(pedido, ana)
    canal = await _conectar(usuario)

    await sync_to_async(retirar)(pedido)

    assert (await canal.receive_json_from(timeout=5))["pedido_id"] == pedido.id
    await canal.disconnect()


# --- Criterio 3: al cambiar de estado (p. ej. entregado) la lista se refresca ---


async def test_cambio_de_estado_de_su_pedido_avisa_al_repartidor():
    sede = await sync_to_async(_sede)()
    usuario, ana = await sync_to_async(_repartidor)("ana@correo.com", sede)
    pedido = await sync_to_async(_pedido)(sede)
    await sync_to_async(asignar)(pedido, ana)
    canal = await _conectar(usuario)

    await sync_to_async(cambiar_estado)(pedido, E.RECOGIDO, usuario, REPARTIDOR)

    assert (await canal.receive_json_from(timeout=5))["pedido_id"] == pedido.id
    await canal.disconnect()


async def test_cada_repartidor_solo_recibe_lo_suyo():
    sede = await sync_to_async(_sede)()
    usuario_ana, ana = await sync_to_async(_repartidor)("ana@correo.com", sede)
    usuario_luis, _ = await sync_to_async(_repartidor)("luis@correo.com", sede)
    pedido = await sync_to_async(_pedido)(sede)
    canal_ana = await _conectar(usuario_ana)
    canal_luis = await _conectar(usuario_luis)

    await sync_to_async(asignar)(pedido, ana)

    assert (await canal_ana.receive_json_from(timeout=5))["pedido_id"] == pedido.id
    assert await canal_luis.receive_nothing(timeout=0.5)
    await canal_ana.disconnect()
    await canal_luis.disconnect()


# --- Criterio 1: canal privado del repartidor ------------------------------------


async def test_sin_token_o_token_invalido_es_rechazado():
    assert (await WebsocketCommunicator(application, RUTA).connect())[0] is False
    assert (await WebsocketCommunicator(application, f"{RUTA}?token=basura").connect())[0] is False


async def test_otros_roles_o_sin_perfil_de_repartidor_son_rechazados():
    sede = await sync_to_async(_sede)()
    operador, _ = await sync_to_async(_personal)(OPERADOR, "operador@correo.com", sede)
    # Tiene el rol pero no el perfil de repartidor.
    sin_perfil, _ = await sync_to_async(_personal)(REPARTIDOR, "sinperfil@correo.com", sede)

    for usuario in (operador, sin_perfil):
        assert (await _canal(usuario).connect())[0] is False
