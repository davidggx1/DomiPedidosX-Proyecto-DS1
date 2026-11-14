"""Pruebas de HU-37 · Estado de los repartidores y sus pedidos asignados."""
import pytest
from asgiref.sync import sync_to_async
from channels.testing import WebsocketCommunicator
from django.contrib.auth.models import Group
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from config.asgi import application
from pedidos.asignacion import asignar, retirar
from pedidos.estados import cambiar_estado
from pedidos.models import EstadoPedido as E
from pedidos.models import Pedido
from pedidos.repartidores_estado import avance_pedido, estado_logistico
from sedes.models import Ciudad, Sede
from usuarios.models import Empleado, Repartidor, Usuario
from usuarios.roles import ADMINISTRADOR, COCINA, OPERADOR, REPARTIDOR

URL = "/api/pedidos/repartidores/estado/"
URL_DISPONIBILIDAD = "/api/usuarios/repartidor/disponibilidad/"
RUTA_WS = "/ws/pedidos/repartidores/"

def _sede(nombre="Centro"):
    ciudad, _ = Ciudad.objects.get_or_create(nombre="Cali")
    return Sede.objects.create(
        ciudad=ciudad, nombre=nombre, direccion="Calle 1 # 2-3", latitud=3.45,
        longitud=-76.53, barrio="Granada", telefono="3000000000", correo="s@correo.com",
    )


def _personal(rol, email, sede, nombres="N"):
    usuario = Usuario.objects.create_user(username=email, email=email, password="ClaveSegura2026")
    usuario.groups.add(Group.objects.get_or_create(name=rol)[0])
    empleado = Empleado.objects.create(
        usuario=usuario, sede=sede, tipo_documento="CC", num_documento=email[:10],
        nombres=nombres, apellidos="A", celular="3001234567", direccion="Calle 4",
    )
    return usuario, empleado


def _repartidor(email, sede, disponible=True, nombres="N"):
    usuario, empleado = _personal(REPARTIDOR, email, sede, nombres)
    return usuario, Repartidor.objects.create(empleado=empleado, disponible=disponible)


def _pedido(sede, numero="P-1", estado=E.LISTO_DESPACHO):
    return Pedido.objects.create(numero_pedido=numero, sede=sede, estado=estado)


def _cliente_api(usuario):
    cliente = APIClient()
    cliente.force_authenticate(usuario)
    return cliente


def _canal(usuario):
    token = str(AccessToken.for_user(usuario))
    return WebsocketCommunicator(application, f"{RUTA_WS}?token={token}")


async def _conectar(usuario):
    canal = _canal(usuario)
    conectado, _ = await canal.connect()
    assert conectado
    return canal


# --- Lógica pura ----------------------------------------------------------------


def test_estado_logistico():
    assert estado_logistico(True, 0) == "disponible"
    assert estado_logistico(False, 0) == "no_disponible"
    assert estado_logistico(True, 2) == "en_entrega"
    # Se puso "No disponible" pero aún tiene entregas: sigue "En entrega".
    assert estado_logistico(False, 1) == "en_entrega"


def test_avance_del_pedido():
    assert avance_pedido(E.LISTO_DESPACHO) == {"paso": 1, "total": 4}
    assert avance_pedido(E.RECOGIDO) == {"paso": 2, "total": 4}
    assert avance_pedido(E.EN_CAMINO) == {"paso": 3, "total": 4}
    assert avance_pedido(E.ENTREGADO) == {"paso": 4, "total": 4}
    assert avance_pedido(E.EN_PREPARACION)["paso"] == 0


# --- Criterio 1: listado de la sede y su estado -----------------------------------


@pytest.mark.django_db
def test_el_operador_ve_los_repartidores_de_su_sede_con_su_estado():
    sede = _sede()
    operador, _ = _personal(OPERADOR, "operador@correo.com", sede)
    _repartidor("ana@correo.com", sede, disponible=True, nombres="Ana")
    _repartidor("beto@correo.com", sede, disponible=False, nombres="Beto")
    _, carla = _repartidor("carla@correo.com", sede, disponible=True, nombres="Carla")
    asignar(_pedido(sede), carla)

    respuesta = _cliente_api(operador).get(URL)

    assert respuesta.status_code == 200
    estados = {item["nombres"]: item["estado"] for item in respuesta.json()}
    assert estados == {"Ana": "disponible", "Beto": "no_disponible", "Carla": "en_entrega"}
    nombres = {item["nombres"]: item["estado_nombre"] for item in respuesta.json()}
    assert nombres["Carla"] == "En entrega"


@pytest.mark.django_db
def test_el_operador_no_ve_repartidores_de_otras_sedes():
    centro, norte = _sede("Centro"), _sede("Norte")
    operador, _ = _personal(OPERADOR, "operador@correo.com", centro)
    _repartidor("ana@correo.com", centro, nombres="Ana")
    _repartidor("luis@correo.com", norte, nombres="Luis")

    respuesta = _cliente_api(operador).get(URL)

    assert [item["nombres"] for item in respuesta.json()] == ["Ana"]


@pytest.mark.django_db
def test_el_administrador_ve_todas_las_sedes():
    centro, norte = _sede("Centro"), _sede("Norte")
    admin, _ = _personal(ADMINISTRADOR, "admin@correo.com", None)
    _repartidor("ana@correo.com", centro, nombres="Ana")
    _repartidor("luis@correo.com", norte, nombres="Luis")

    respuesta = _cliente_api(admin).get(URL)

    assert sorted(item["nombres"] for item in respuesta.json()) == ["Ana", "Luis"]


@pytest.mark.django_db
def test_los_repartidores_inactivos_no_aparecen():
    sede = _sede()
    operador, _ = _personal(OPERADOR, "operador@correo.com", sede)
    usuario, _ = _repartidor("ana@correo.com", sede)
    usuario.is_active = False
    usuario.save()

    assert _cliente_api(operador).get(URL).json() == []


@pytest.mark.django_db
def test_solo_operador_y_administrador_pueden_consultar():
    sede = _sede()
    cocina, _ = _personal(COCINA, "cocina@correo.com", sede)
    repartidor, _ = _repartidor("ana@correo.com", sede)

    assert APIClient().get(URL).status_code == 401
    assert _cliente_api(cocina).get(URL).status_code == 403
    assert _cliente_api(repartidor).get(URL).status_code == 403


# --- Criterio 3: al seleccionarlo se ven sus pedidos y su avance --------------------


@pytest.mark.django_db
def test_cada_repartidor_trae_sus_pedidos_en_curso_con_su_avance():
    sede = _sede()
    operador, _ = _personal(OPERADOR, "operador@correo.com", sede)
    _, ana = _repartidor("ana@correo.com", sede, nombres="Ana")
    _, luis = _repartidor("luis@correo.com", sede, nombres="Luis")
    # asignar() solo deja un pedido por repartidor; aquí se crean directo para probar
    # que el listado devuelve todos los que tenga en curso, cada uno con su avance.
    Pedido.objects.create(numero_pedido="P-1", sede=sede, estado=E.LISTO_DESPACHO, repartidor=ana)
    Pedido.objects.create(numero_pedido="P-2", sede=sede, estado=E.RECOGIDO, repartidor=ana)
    asignar(_pedido(sede, "P-3"), luis)

    respuesta = _cliente_api(operador).get(URL).json()
    por_nombre = {item["nombres"]: item for item in respuesta}

    assert por_nombre["Ana"]["carga"] == 2
    assert por_nombre["Luis"]["carga"] == 1
    pedidos_ana = {p["numero_pedido"]: p for p in por_nombre["Ana"]["pedidos"]}
    assert set(pedidos_ana) == {"P-1", "P-2"}
    assert pedidos_ana["P-1"]["avance"] == {"paso": 1, "total": 4}
    assert pedidos_ana["P-2"]["avance"] == {"paso": 2, "total": 4}
    assert pedidos_ana["P-2"]["estado_nombre"] == "Recogido"


@pytest.mark.django_db
def test_un_pedido_entregado_ya_no_cuenta_en_la_carga():
    sede = _sede()
    operador, _ = _personal(OPERADOR, "operador@correo.com", sede)
    _, ana = _repartidor("ana@correo.com", sede, nombres="Ana")
    Pedido.objects.create(numero_pedido="P-9", sede=sede, estado=E.ENTREGADO, repartidor=ana)

    item = _cliente_api(operador).get(URL).json()[0]

    assert item["carga"] == 0
    assert item["pedidos"] == []
    assert item["estado"] == "disponible"


@pytest.mark.django_db
def test_no_disponible_con_pedidos_sigue_en_entrega():
    sede = _sede()
    operador, _ = _personal(OPERADOR, "operador@correo.com", sede)
    _, ana = _repartidor("ana@correo.com", sede, disponible=True)
    asignar(_pedido(sede), ana)
    # Después de recibir el pedido se pone "No disponible" (HU-41, criterio 3).
    Repartidor.objects.filter(pk=ana.pk).update(disponible=False)

    assert _cliente_api(operador).get(URL).json()[0]["estado"] == "en_entrega"


# --- Criterio 2: actualización en tiempo real -------------------------------------


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_el_operador_recibe_aviso_al_asignar_y_al_retirar():
    sede = await sync_to_async(_sede)()
    operador, _ = await sync_to_async(_personal)(OPERADOR, "operador@correo.com", sede)
    _, ana = await sync_to_async(_repartidor)("ana@correo.com", sede)
    pedido = await sync_to_async(_pedido)(sede)
    canal = await _conectar(operador)

    await sync_to_async(asignar)(pedido, ana)
    assert (await canal.receive_json_from(timeout=5))["tipo"] == "repartidores_actualizados"

    await sync_to_async(retirar)(pedido)
    assert (await canal.receive_json_from(timeout=5))["tipo"] == "repartidores_actualizados"
    await canal.disconnect()


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_el_operador_recibe_aviso_cuando_un_pedido_cambia_de_estado():
    sede = await sync_to_async(_sede)()
    operador, _ = await sync_to_async(_personal)(OPERADOR, "operador@correo.com", sede)
    usuario, ana = await sync_to_async(_repartidor)("ana@correo.com", sede)
    pedido = await sync_to_async(_pedido)(sede)
    await sync_to_async(asignar)(pedido, ana)
    canal = await _conectar(operador)

    await sync_to_async(cambiar_estado)(pedido, E.RECOGIDO, usuario, REPARTIDOR)

    assert (await canal.receive_json_from(timeout=5))["tipo"] == "repartidores_actualizados"
    await canal.disconnect()


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_el_operador_recibe_aviso_cuando_el_repartidor_cambia_su_disponibilidad():
    sede = await sync_to_async(_sede)()
    operador, _ = await sync_to_async(_personal)(OPERADOR, "operador@correo.com", sede)
    usuario, _ = await sync_to_async(_repartidor)("ana@correo.com", sede, disponible=False)
    canal = await _conectar(operador)

    respuesta = await sync_to_async(_cliente_api(usuario).patch)(
        URL_DISPONIBILIDAD, {"disponible": True}, format="json"
    )

    assert respuesta.status_code == 200
    assert (await canal.receive_json_from(timeout=5))["tipo"] == "repartidores_actualizados"
    await canal.disconnect()


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_un_operador_no_recibe_avisos_de_otra_sede():
    centro = await sync_to_async(_sede)("Centro")
    norte = await sync_to_async(_sede)("Norte")
    operador, _ = await sync_to_async(_personal)(OPERADOR, "operador@correo.com", centro)
    _, luis = await sync_to_async(_repartidor)("luis@correo.com", norte)
    pedido = await sync_to_async(_pedido)(norte)
    canal = await _conectar(operador)

    await sync_to_async(asignar)(pedido, luis)

    assert await canal.receive_nothing(timeout=0.5)
    await canal.disconnect()


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_el_administrador_recibe_avisos_de_cualquier_sede():
    sede = await sync_to_async(_sede)()
    admin, _ = await sync_to_async(_personal)(ADMINISTRADOR, "admin@correo.com", None)
    _, ana = await sync_to_async(_repartidor)("ana@correo.com", sede)
    pedido = await sync_to_async(_pedido)(sede)
    canal = await _conectar(admin)

    await sync_to_async(asignar)(pedido, ana)

    assert (await canal.receive_json_from(timeout=5))["tipo"] == "repartidores_actualizados"
    await canal.disconnect()


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_sin_token_u_otros_roles_son_rechazados():
    sede = await sync_to_async(_sede)()
    repartidor, _ = await sync_to_async(_repartidor)("ana@correo.com", sede)
    cocina, _ = await sync_to_async(_personal)(COCINA, "cocina@correo.com", sede)

    assert (await WebsocketCommunicator(application, RUTA_WS).connect())[0] is False
    assert (await WebsocketCommunicator(application, f"{RUTA_WS}?token=basura").connect())[0] is False
    for usuario in (repartidor, cocina):
        assert (await _canal(usuario).connect())[0] is False