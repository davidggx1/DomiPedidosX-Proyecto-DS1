"""Pruebas de HU-47 · Seguimiento del pedido en tiempo real (Cliente)."""
import time
from datetime import date
from decimal import Decimal

import pytest
from asgiref.sync import sync_to_async
from channels.testing import WebsocketCommunicator
from django.contrib.auth.models import Group
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from config.asgi import application
from pedidos.aprobacion import aprobar_pedido
from pedidos.estados import cambiar_estado
from pedidos.models import EstadoPedido as E
from pedidos.models import Factura, MetodoPago, Pedido
from sedes.models import Ciudad, Sede
from usuarios.models import Cliente, Empleado, Repartidor, Usuario
from usuarios.roles import COCINA, OPERADOR, REPARTIDOR

MIOS = "/api/pedidos/mios/"
CLAVE = "ClaveSegura2026"


# --- Datos de prueba ------------------------------------------------------------


def _sede():
    ciudad, _ = Ciudad.objects.get_or_create(nombre="Cali")
    return Sede.objects.create(
        ciudad=ciudad, nombre="Centro", direccion="Calle 1 # 2-3", latitud=3.45,
        longitud=-76.53, barrio="Granada", telefono="3000000000", correo="s@correo.com",
    )


def _cliente(email, celular):
    usuario = Usuario.objects.create_user(username=email, email=email, password=CLAVE)
    return Cliente.objects.create(
        usuario=usuario, tipo_documento="CC", num_documento=celular, nombres="Laura",
        apellidos="Gómez", celular=celular, fecha_nacimiento=date(2000, 1, 1),
    )


def _personal(rol, email, sede):
    usuario = Usuario.objects.create_user(username=email, email=email, password=CLAVE)
    usuario.groups.add(Group.objects.get_or_create(name=rol)[0])
    empleado = Empleado.objects.create(
        usuario=usuario, sede=sede, tipo_documento="CC", num_documento=email[:10],
        nombres="N", apellidos="A", celular="3001234567", direccion="Calle 4",
    )
    if rol == REPARTIDOR:
        Repartidor.objects.create(empleado=empleado, disponible=True)
    return usuario


def _pedido(sede, cliente, numero, estado=E.PENDIENTE_APROBACION, total=None, **extra):
    pedido = Pedido.objects.create(sede=sede, cliente=cliente, numero_pedido=numero, estado=estado, **extra)
    if total is not None:
        Factura.objects.create(
            pedido=pedido, numero=f"F-{numero}", subtotal=Decimal(total), iva=Decimal("0"),
            costo_domicilio=Decimal("0"), total=Decimal(total), metodo_pago=MetodoPago.TARJETA,
        )
    return pedido


def _canal(usuario, pedido):
    token = str(AccessToken.for_user(usuario))
    return WebsocketCommunicator(application, f"/ws/pedidos/{pedido.id}/estado/?token={token}")


async def _conectar(usuario, pedido):
    canal = _canal(usuario, pedido)
    conectado, _ = await canal.connect()
    assert conectado
    return canal


# --- Mis pedidos (lista del cliente) --------------------------------------------


@pytest.mark.django_db
def test_mis_pedidos_solo_trae_los_del_cliente_con_los_activos_primero():
    sede = _sede()
    laura = _cliente("laura@correo.com", "3101112233")
    pedro = _cliente("pedro@correo.com", "3104445566")
    _pedido(sede, laura, "P-ENTREGADO", E.ENTREGADO)
    _pedido(sede, laura, "P-EN-CAMINO", E.EN_CAMINO, total="35000")
    _pedido(sede, laura, "P-CANCELADO", E.CANCELADO)
    _pedido(sede, pedro, "P-DE-PEDRO", E.RECIBIDO)
    api = APIClient()
    api.force_authenticate(laura.usuario)

    respuesta = api.get(MIOS)

    assert respuesta.status_code == 200
    numeros = [p["numero_pedido"] for p in respuesta.data]
    assert numeros[0] == "P-EN-CAMINO"
    assert set(numeros) == {"P-ENTREGADO", "P-EN-CAMINO", "P-CANCELADO"}
    activo = respuesta.data[0]
    assert activo["estado_nombre"] == "En camino"
    assert activo["total"] == "35000.00"


@pytest.mark.django_db
def test_mis_pedidos_es_solo_para_clientes():
    operador = _personal(OPERADOR, "operador@correo.com", _sede())
    api = APIClient()

    assert api.get(MIOS).status_code == 401
    api.force_authenticate(operador)
    assert api.get(MIOS).status_code == 403


@pytest.mark.django_db
def test_el_cliente_consulta_estado_e_historial_de_su_pedido():
    """Carga inicial de la barra de progreso (endpoint existente de HU-31)."""
    sede = _sede()
    laura = _cliente("laura@correo.com", "3101112233")
    operador = _personal(OPERADOR, "operador@correo.com", sede)
    pedido = _pedido(sede, laura, "P-1")
    aprobar_pedido(usuario=operador, pedido_id=pedido.id)
    api = APIClient()
    api.force_authenticate(laura.usuario)

    respuesta = api.get(f"/api/pedidos/{pedido.id}/estado/")

    assert respuesta.status_code == 200
    assert respuesta.data["estado"] == E.RECIBIDO
    assert [h["estado"] for h in respuesta.data["historial"]] == [E.RECIBIDO]


# --- Criterio 1: barra de progreso en tiempo real (<10 s) -----------------------


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_la_aprobacion_llega_al_cliente_en_menos_de_10s():
    sede = await sync_to_async(_sede)()
    laura = await sync_to_async(_cliente)("laura@correo.com", "3101112233")
    operador = await sync_to_async(_personal)(OPERADOR, "operador@correo.com", sede)
    pedido = await sync_to_async(_pedido)(sede, laura, "P-1")
    canal = await _conectar(laura.usuario, pedido)

    inicio = time.monotonic()
    await sync_to_async(aprobar_pedido)(usuario=operador, pedido_id=pedido.id)
    evento = await canal.receive_json_from(timeout=10)

    assert time.monotonic() - inicio < 10
    assert evento["tipo"] == "estado_pedido_cambiado"
    assert evento["estado_anterior"] == E.PENDIENTE_APROBACION
    assert evento["estado"] == E.RECIBIDO
    assert evento["estado_nombre"] == "Recibido"
    assert evento["fecha_hora"]
    await canal.disconnect()


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_el_cliente_recibe_cada_paso_de_cocina_y_entrega():
    sede = await sync_to_async(_sede)()
    laura = await sync_to_async(_cliente)("laura@correo.com", "3101112233")
    cocina = await sync_to_async(_personal)(COCINA, "cocina@correo.com", sede)
    repartidor = await sync_to_async(_personal)(REPARTIDOR, "rep@correo.com", sede)
    perfil = await sync_to_async(Repartidor.objects.get)(empleado__usuario=repartidor)
    pedido = await sync_to_async(_pedido)(sede, laura, "P-1", E.RECIBIDO, repartidor=perfil)
    canal = await _conectar(laura.usuario, pedido)

    pasos = [
        (E.EN_PREPARACION, cocina, COCINA),
        (E.LISTO_DESPACHO, cocina, COCINA),
        (E.RECOGIDO, repartidor, REPARTIDOR),
        (E.EN_CAMINO, repartidor, REPARTIDOR),
        (E.ENTREGADO, repartidor, REPARTIDOR),
    ]
    recibidos = []
    for estado, usuario, rol in pasos:
        await sync_to_async(cambiar_estado)(pedido, estado, usuario, rol)
        recibidos.append((await canal.receive_json_from(timeout=5))["estado"])

    assert recibidos == [estado for estado, _, _ in pasos]
    await canal.disconnect()


# --- Criterio 2: mensaje de cancelación ----------------------------------------


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_la_cancelacion_llega_con_su_motivo():
    sede = await sync_to_async(_sede)()
    laura = await sync_to_async(_cliente)("laura@correo.com", "3101112233")
    operador = await sync_to_async(_personal)(OPERADOR, "operador@correo.com", sede)
    pedido = await sync_to_async(_pedido)(sede, laura, "P-1", E.RECIBIDO)
    canal = await _conectar(laura.usuario, pedido)

    await sync_to_async(cambiar_estado)(pedido, E.CANCELADO, operador, OPERADOR, "Se agotó el pan")
    evento = await canal.receive_json_from(timeout=5)

    assert evento["estado"] == E.CANCELADO
    assert evento["motivo_cancelacion"] == "Se agotó el pan"
    await canal.disconnect()


# --- Privacidad del canal ------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_un_cliente_no_puede_seguir_el_pedido_de_otro():
    sede = await sync_to_async(_sede)()
    laura = await sync_to_async(_cliente)("laura@correo.com", "3101112233")
    pedro = await sync_to_async(_cliente)("pedro@correo.com", "3104445566")
    pedido = await sync_to_async(_pedido)(sede, laura, "P-1")

    conectado, codigo = await _canal(pedro.usuario, pedido).connect()

    assert conectado is False
    assert codigo == 4403


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_cada_cliente_solo_recibe_su_pedido():
    sede = await sync_to_async(_sede)()
    laura = await sync_to_async(_cliente)("laura@correo.com", "3101112233")
    pedro = await sync_to_async(_cliente)("pedro@correo.com", "3104445566")
    operador = await sync_to_async(_personal)(OPERADOR, "operador@correo.com", sede)
    de_laura = await sync_to_async(_pedido)(sede, laura, "P-LAURA")
    de_pedro = await sync_to_async(_pedido)(sede, pedro, "P-PEDRO")
    canal_laura = await _conectar(laura.usuario, de_laura)
    canal_pedro = await _conectar(pedro.usuario, de_pedro)

    await sync_to_async(aprobar_pedido)(usuario=operador, pedido_id=de_laura.id)

    assert (await canal_laura.receive_json_from(timeout=5))["numero_pedido"] == "P-LAURA"
    assert await canal_pedro.receive_nothing(timeout=0.5)
    await canal_laura.disconnect()
    await canal_pedro.disconnect()
