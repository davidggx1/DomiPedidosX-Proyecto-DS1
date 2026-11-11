"""HU-60: capacity alerts for the operator, by WebSocket."""
from datetime import time

import pytest
from asgiref.sync import sync_to_async
from channels.testing import WebsocketCommunicator
from django.contrib.auth.models import Group
from rest_framework_simplejwt.tokens import AccessToken

from config.asgi import application
from pedidos import alertas_capacidad
from pedidos.alertas_capacidad import (
    ALERTA_ACTIVADA,
    ALERTA_DESACTIVADA,
    transicion_de_alerta,
)
from pedidos.estados import cambiar_estado
from pedidos.models import EstadoPedido, Pedido
from sedes.models import CapacidadSede, Ciudad, Sede
from usuarios.models import Empleado, Usuario
from usuarios.roles import COCINA

pytestmark = [pytest.mark.asyncio, pytest.mark.django_db(transaction=True)]

E = EstadoPedido
TODOS_LOS_DIAS = "lunes,martes,miercoles,jueves,viernes,sabado,domingo"


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


def _franja(sede, maximo=5, umbral=4):
    # all day, every day, so the test does not depend on the clock
    return CapacidadSede.objects.create(
        sede=sede, hora_inicio=time(0, 0), hora_fin=time(23, 59, 59),
        dias_semana=TODOS_LOS_DIAS, max_pedidos_simultaneos=maximo, umbral_alerta=umbral,
    )


def _pedido(sede, numero, estado=E.RECIBIDO):
    return Pedido.objects.create(numero_pedido=numero, sede=sede, estado=estado)


def _mover(pedido, estado):
    pedido.estado = estado
    pedido.save(update_fields=["estado"])


def _canal(usuario):
    token = str(AccessToken.for_user(usuario))
    return WebsocketCommunicator(application, f"/ws/pedidos/entrantes/?token={token}")


async def _operador_conectado(sede, email="op@correo.com"):
    operador = await sync_to_async(_personal)("operador", email, sede)
    canal = _canal(operador)
    assert (await canal.connect())[0]
    return canal


async def _evento(canal):
    datos = await canal.receive_json_from(timeout=5)
    assert datos["tipo"] == "capacidad_actualizada"
    return datos


# --- Criterio 1 y 2: alerta al alcanzar el umbral, con ocupación vs límite ---------

async def test_avisa_la_ocupacion_y_activa_la_alerta_al_cruzar_el_umbral():
    sede = await sync_to_async(_sede)("Norte")
    await sync_to_async(_franja)(sede, maximo=5, umbral=4)
    canal = await _operador_conectado(sede)

    for numero in range(1, 4):
        await sync_to_async(_pedido)(sede, f"P-{numero}")
        datos = await _evento(canal)
        assert datos["transicion"] is None
        assert datos["capacidad"]["activos"] == numero
        assert datos["capacidad"]["en_alerta"] is False

    await sync_to_async(_pedido)(sede, "P-4")
    datos = await _evento(canal)

    assert datos["transicion"] == ALERTA_ACTIVADA
    capacidad = datos["capacidad"]
    assert (capacidad["activos"], capacidad["maximo"], capacidad["porcentaje"]) == (4, 5, 80)
    assert capacidad["en_alerta"] is True and capacidad["estado"] == "disponible"
    await canal.disconnect()


# --- Criterio 3: no se duplica sobre el umbral y se apaga al bajar -------------------

async def test_no_repite_la_alerta_mientras_siga_sobre_el_umbral():
    sede = await sync_to_async(_sede)("Norte")
    await sync_to_async(_franja)(sede, maximo=5, umbral=4)
    for numero in range(1, 4):
        await sync_to_async(_pedido)(sede, f"P-{numero}")
    canal = await _operador_conectado(sede)

    await sync_to_async(_pedido)(sede, "P-4")
    assert (await _evento(canal))["transicion"] == ALERTA_ACTIVADA

    await sync_to_async(_pedido)(sede, "P-5")
    datos = await _evento(canal)

    assert datos["transicion"] is None
    assert datos["capacidad"]["en_alerta"] is True
    assert datos["capacidad"]["estado"] == "saturada"
    await canal.disconnect()


async def test_se_apaga_al_bajar_del_umbral():
    sede = await sync_to_async(_sede)("Norte")
    await sync_to_async(_franja)(sede, maximo=5, umbral=4)
    pedidos = [await sync_to_async(_pedido)(sede, f"P-{n}") for n in range(1, 6)]
    canal = await _operador_conectado(sede)

    # 5 -> 4: still on the umbral, nothing turns off
    await sync_to_async(_mover)(pedidos[0], E.LISTO_DESPACHO)
    datos = await _evento(canal)
    assert datos["transicion"] is None
    assert datos["capacidad"]["en_alerta"] is True

    # 4 -> 3: under the umbral, the alert turns off
    await sync_to_async(_mover)(pedidos[1], E.CANCELADO)
    datos = await _evento(canal)
    assert datos["transicion"] == ALERTA_DESACTIVADA
    assert datos["capacidad"]["en_alerta"] is False
    assert datos["capacidad"]["activos"] == 3
    await canal.disconnect()


async def test_vuelve_a_activarse_si_la_sede_se_llena_otra_vez():
    sede = await sync_to_async(_sede)("Norte")
    await sync_to_async(_franja)(sede, maximo=5, umbral=4)
    pedidos = [await sync_to_async(_pedido)(sede, f"P-{n}") for n in range(1, 5)]
    canal = await _operador_conectado(sede)

    await sync_to_async(_mover)(pedidos[0], E.CANCELADO)
    assert (await _evento(canal))["transicion"] == ALERTA_DESACTIVADA

    await sync_to_async(_pedido)(sede, "P-5")
    assert (await _evento(canal))["transicion"] == ALERTA_ACTIVADA
    await canal.disconnect()


async def test_el_flujo_de_cocina_libera_cupo_al_pasar_a_listo_para_despacho():
    sede = await sync_to_async(_sede)("Norte")
    await sync_to_async(_franja)(sede, maximo=2, umbral=2)
    cocina = await sync_to_async(_personal)("cocina", "co@correo.com", sede)
    p1 = await sync_to_async(_pedido)(sede, "P-1")
    await sync_to_async(_pedido)(sede, "P-2")
    canal = await _operador_conectado(sede)

    # recibido -> en_preparacion keeps using the slot: no event
    await sync_to_async(cambiar_estado)(p1, E.EN_PREPARACION, cocina, COCINA)
    assert await canal.receive_nothing(timeout=0.5)

    await sync_to_async(cambiar_estado)(p1, E.LISTO_DESPACHO, cocina, COCINA)
    datos = await _evento(canal)
    assert datos["transicion"] == ALERTA_DESACTIVADA
    assert datos["capacidad"]["activos"] == 1
    await canal.disconnect()


# --- Qué NO avisa -----------------------------------------------------------------

async def test_no_avisa_si_el_pedido_sigue_ocupando_cupo():
    sede = await sync_to_async(_sede)("Norte")
    await sync_to_async(_franja)(sede)
    pedido = await sync_to_async(_pedido)(sede, "P-1", E.PENDIENTE_APROBACION)
    canal = await _operador_conectado(sede)

    await sync_to_async(_mover)(pedido, E.RECIBIDO)
    await sync_to_async(_mover)(pedido, E.EN_PREPARACION)

    assert await canal.receive_nothing(timeout=0.5)
    await canal.disconnect()


async def test_no_avisa_si_se_guarda_otro_campo_del_pedido():
    sede = await sync_to_async(_sede)("Norte")
    await sync_to_async(_franja)(sede)
    pedido = await sync_to_async(_pedido)(sede, "P-1")
    canal = await _operador_conectado(sede)

    pedido.numero_pedido = "P-9"
    await sync_to_async(pedido.save)(update_fields=["numero_pedido"])

    assert await canal.receive_nothing(timeout=0.5)
    await canal.disconnect()


async def test_la_alerta_solo_llega_a_los_operadores_de_su_sede():
    norte = await sync_to_async(_sede)("Norte")
    sur = await sync_to_async(_sede)("Sur")
    await sync_to_async(_franja)(norte)
    await sync_to_async(_franja)(sur)
    canal_norte = await _operador_conectado(norte, "op_norte@correo.com")
    canal_sur = await _operador_conectado(sur, "op_sur@correo.com")
    admin = await sync_to_async(_personal)("administrador", "ad@correo.com")
    canal_admin = _canal(admin)
    assert (await canal_admin.connect())[0]

    await sync_to_async(_pedido)(norte, "P-N")

    assert (await _evento(canal_norte))["capacidad"]["sede"] == norte.pk
    assert await canal_sur.receive_nothing(timeout=0.5)
    assert await canal_admin.receive_nothing(timeout=0.5)
    for canal in (canal_norte, canal_sur, canal_admin):
        await canal.disconnect()


# --- Cambios de franja y sede sin franja --------------------------------------------

async def test_avisa_cuando_el_administrador_cambia_la_franja():
    sede = await sync_to_async(_sede)("Norte")
    franja = await sync_to_async(_franja)(sede, maximo=10, umbral=8)
    canal = await _operador_conectado(sede)

    franja.max_pedidos_simultaneos = 20
    franja.umbral_alerta = 16
    await sync_to_async(franja.save)()

    datos = await _evento(canal)
    assert datos["transicion"] is None
    assert (datos["capacidad"]["maximo"], datos["capacidad"]["umbral_alerta"]) == (20, 16)
    await canal.disconnect()


async def test_sede_sin_franja_no_envia_eventos_por_pedidos():
    sede = await sync_to_async(_sede)("Norte")
    canal = await _operador_conectado(sede)

    await sync_to_async(_pedido)(sede, "P-1")

    assert await canal.receive_nothing(timeout=0.5)
    await canal.disconnect()


async def test_borrar_la_ultima_franja_avisa_que_la_sede_quedo_sin_franja():
    sede = await sync_to_async(_sede)("Norte")
    franja = await sync_to_async(_franja)(sede)
    canal = await _operador_conectado(sede)

    await sync_to_async(franja.delete)()

    datos = await _evento(canal)
    assert datos["transicion"] is None
    assert datos["capacidad"]["estado"] == "sin_franja"
    assert datos["capacidad"]["maximo"] is None and datos["capacidad"]["en_alerta"] is False
    await canal.disconnect()


# --- Robustez ----------------------------------------------------------------------

async def test_un_fallo_del_canal_no_rompe_el_pedido(monkeypatch):
    sede = await sync_to_async(_sede)("Norte")
    await sync_to_async(_franja)(sede)

    def canal_roto():
        raise RuntimeError("redis caido")

    monkeypatch.setattr(alertas_capacidad, "get_channel_layer", canal_roto)

    pedido = await sync_to_async(_pedido)(sede, "P-1")

    assert await Pedido.objects.filter(pk=pedido.pk).aexists()


async def test_transicion_de_alerta_solo_marca_el_cruce():
    assert transicion_de_alerta(activos=4, umbral=4, cambio=1) == ALERTA_ACTIVADA
    assert transicion_de_alerta(activos=5, umbral=4, cambio=1) is None
    assert transicion_de_alerta(activos=3, umbral=4, cambio=1) is None
    assert transicion_de_alerta(activos=3, umbral=4, cambio=-1) == ALERTA_DESACTIVADA
    assert transicion_de_alerta(activos=4, umbral=4, cambio=-1) is None
    assert transicion_de_alerta(activos=2, umbral=4, cambio=-1) is None
    assert transicion_de_alerta(activos=4, umbral=4, cambio=0) is None
