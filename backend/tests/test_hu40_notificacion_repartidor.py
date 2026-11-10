"""Pruebas de HU-40 · Notificación de asignación al repartidor (SCRUM-115)."""
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


def _pedido(sede, numero="P-100"):
    return Pedido.objects.create(numero_pedido=numero, sede=sede, estado=E.LISTO_DESPACHO)


async def _conectar(usuario):
    token = str(AccessToken.for_user(usuario))
    canal = WebsocketCommunicator(application, f"{RUTA}?token={token}")
    conectado, _ = await canal.connect()
    assert conectado
    return canal


# --- Criterio 1: aviso en menos de 10 segundos -------------------------------


async def test_al_asignar_llega_el_aviso_en_menos_de_10_segundos():
    sede = await sync_to_async(_sede)()
    usuario, ana = await sync_to_async(_repartidor)("ana@correo.com", sede)
    pedido = await sync_to_async(_pedido)(sede)
    canal = await _conectar(usuario)

    inicio = time.monotonic()
    await sync_to_async(asignar)(pedido, ana)
    data = await canal.receive_json_from(timeout=10)

    assert time.monotonic() - inicio < 10
    assert data["aviso"]["tipo"] == "asignado"
    assert data["aviso"]["numero_pedido"] == "P-100"
    assert "P-100" in data["aviso"]["mensaje"]
    await canal.disconnect()


# --- Criterio 2: el aviso trae con qué abrir el detalle ----------------------


async def test_el_aviso_trae_el_id_para_abrir_el_detalle():
    sede = await sync_to_async(_sede)()
    usuario, ana = await sync_to_async(_repartidor)("ana@correo.com", sede)
    pedido = await sync_to_async(_pedido)(sede)
    canal = await _conectar(usuario)

    await sync_to_async(asignar)(pedido, ana)

    assert (await canal.receive_json_from(timeout=5))["pedido_id"] == pedido.id
    await canal.disconnect()


# --- Criterio 3: aviso de retiro por reasignación o cancelación --------------


async def test_al_reasignar_el_anterior_recibe_aviso_de_retiro():
    sede = await sync_to_async(_sede)()
    usuario, ana = await sync_to_async(_repartidor)("ana@correo.com", sede)
    pedido = await sync_to_async(_pedido)(sede)
    await sync_to_async(asignar)(pedido, ana)
    canal = await _conectar(usuario)

    await sync_to_async(retirar)(pedido)
    aviso = (await canal.receive_json_from(timeout=5))["aviso"]

    assert aviso["tipo"] == "retirado"
    assert aviso["motivo"] == "reasignado"
    await canal.disconnect()


async def test_al_cancelar_el_repartidor_recibe_aviso_de_cancelacion():
    sede = await sync_to_async(_sede)()
    usuario, ana = await sync_to_async(_repartidor)("ana@correo.com", sede)
    operador, _ = await sync_to_async(_personal)(OPERADOR, "operador@correo.com", sede)
    pedido = await sync_to_async(_pedido)(sede)
    await sync_to_async(asignar)(pedido, ana)
    canal = await _conectar(usuario)

    await sync_to_async(cambiar_estado)(pedido, E.CANCELADO, operador, OPERADOR, "Cliente no responde")
    aviso = (await canal.receive_json_from(timeout=5))["aviso"]

    assert aviso["tipo"] == "retirado"
    assert aviso["motivo"] == "cancelado"
    assert "cancelado" in aviso["mensaje"]
    await canal.disconnect()


async def test_avanzar_su_propia_entrega_no_genera_aviso():
    sede = await sync_to_async(_sede)()
    usuario, ana = await sync_to_async(_repartidor)("ana@correo.com", sede)
    pedido = await sync_to_async(_pedido)(sede)
    await sync_to_async(asignar)(pedido, ana)
    canal = await _conectar(usuario)

    await sync_to_async(cambiar_estado)(pedido, E.RECOGIDO, usuario, REPARTIDOR)
    data = await canal.receive_json_from(timeout=5)

    assert data["pedido_id"] == pedido.id
    assert "aviso" not in data  # la lista se refresca, pero sin sonido
    await canal.disconnect()


async def test_el_aviso_solo_le_llega_al_repartidor_asignado():
    sede = await sync_to_async(_sede)()
    usuario_ana, ana = await sync_to_async(_repartidor)("ana@correo.com", sede)
    usuario_luis, _ = await sync_to_async(_repartidor)("luis@correo.com", sede)
    pedido = await sync_to_async(_pedido)(sede)
    canal_ana = await _conectar(usuario_ana)
    canal_luis = await _conectar(usuario_luis)

    await sync_to_async(asignar)(pedido, ana)

    assert (await canal_ana.receive_json_from(timeout=5))["aviso"]["tipo"] == "asignado"
    assert await canal_luis.receive_nothing(timeout=0.5)
    await canal_ana.disconnect()
    await canal_luis.disconnect()
