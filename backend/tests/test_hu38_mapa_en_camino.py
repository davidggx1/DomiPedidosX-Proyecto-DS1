"""HU-38 · Mapa de pedidos en camino para el operador, con la ubicación de cada repartidor."""
from datetime import datetime, timedelta

import pytest
from django.contrib.auth.models import Group
from django.utils import timezone
from rest_framework.test import APIClient

from pedidos.models import EstadoPedido as E, Pedido
from sedes.models import Ciudad, Sede
from usuarios.models import Empleado, Repartidor, Usuario
from usuarios.roles import ADMINISTRADOR, COCINA, OPERADOR, REPARTIDOR

pytestmark = pytest.mark.django_db

UBICACION = "/api/pedidos/mis-entregas/ubicacion/"
MAPA = "/api/pedidos/en-camino/mapa/"
AHORA = timezone.make_aware(datetime(2026, 11, 24, 15, 0))


@pytest.fixture(autouse=True)
def reloj(monkeypatch):
    monkeypatch.setattr(timezone, "now", lambda: AHORA)


def _sede(nombre):
    ciudad, _ = Ciudad.objects.get_or_create(nombre="Cali")
    return Sede.objects.create(
        ciudad=ciudad, nombre=nombre, direccion="Calle 1 # 2-3", latitud=3.45, longitud=-76.53,
        barrio="Granada", telefono="3000000000", correo=f"{nombre.lower()}@correo.com",
    )


def _empleado(rol, email, sede=None, nombres="N", apellidos="A"):
    usuario = Usuario.objects.create_user(username=email, email=email, password="x")
    usuario.groups.add(Group.objects.get_or_create(name=rol)[0])
    empleado = Empleado.objects.create(
        usuario=usuario, sede=sede, tipo_documento="CC", num_documento=email[:10], nombres=nombres,
        apellidos=apellidos, celular="3001234567", direccion="Calle 4",
    )
    if rol == REPARTIDOR:
        return Repartidor.objects.create(empleado=empleado, disponible=True)
    return empleado


def _http(usuario):
    api = APIClient()
    api.force_authenticate(usuario)
    return api


def _pedido(sede, numero, repartidor, estado=E.EN_CAMINO):
    return Pedido.objects.create(
        sede=sede, numero_pedido=numero, estado=estado, repartidor=repartidor,
        entrega_direccion="Calle 5 # 10-20", entrega_barrio="San Fernando",
        entrega_latitud=3.43, entrega_longitud=-76.54,
    )


@pytest.fixture
def centro():
    return _sede("Centro")


@pytest.fixture
def carlos(centro):
    return _empleado(REPARTIDOR, "carlos@correo.com", centro, "Carlos", "Ruiz")


# --- El repartidor envía su ubicación ------------------------------------------------


def test_el_repartidor_en_camino_envia_su_ubicacion(centro, carlos):
    _pedido(centro, "P-1", carlos)

    respuesta = _http(carlos.empleado.usuario).post(UBICACION, {"latitud": 3.44, "longitud": -76.535}, format="json")

    assert respuesta.status_code == 204
    carlos.refresh_from_db()
    assert (carlos.latitud, carlos.longitud, carlos.ubicacion_actualizada_en) == (3.44, -76.535, AHORA)


def test_tambien_con_el_pedido_recien_recogido(centro, carlos):
    _pedido(centro, "P-1", carlos, estado=E.RECOGIDO)

    assert _http(carlos.empleado.usuario).post(UBICACION, {"latitud": 3.4, "longitud": -76.5}).status_code == 204


@pytest.mark.parametrize("estado", [None, E.LISTO_DESPACHO, E.ENTREGADO])
def test_sin_pedido_en_camino_no_se_guarda(centro, carlos, estado):
    if estado:
        _pedido(centro, "P-1", carlos, estado=estado)

    respuesta = _http(carlos.empleado.usuario).post(UBICACION, {"latitud": 3.4, "longitud": -76.5})

    assert respuesta.status_code == 409
    carlos.refresh_from_db()
    assert carlos.ubicacion_actualizada_en is None


@pytest.mark.parametrize("datos", [{"latitud": 95, "longitud": -76.5}, {"latitud": 3.4}, {"latitud": "x", "longitud": 1}])
def test_coordenadas_invalidas(centro, carlos, datos):
    _pedido(centro, "P-1", carlos)

    assert _http(carlos.empleado.usuario).post(UBICACION, datos, format="json").status_code == 400


def test_solo_repartidores_envian_ubicacion(centro):
    operador = _empleado(OPERADOR, "op@correo.com", centro)

    assert _http(operador.usuario).post(UBICACION, {"latitud": 3.4, "longitud": -76.5}).status_code == 403


# --- El operador ve el mapa ---------------------------------------------------------------


def test_el_operador_ve_los_pedidos_en_camino_de_su_sede(centro, carlos):
    sur = _sede("Sur")
    otro = _empleado(REPARTIDOR, "otro@correo.com", sur)
    _pedido(centro, "P-1", carlos)
    _pedido(centro, "P-2", carlos, estado=E.LISTO_DESPACHO)
    _pedido(sur, "P-3", otro)
    Repartidor.objects.filter(pk=carlos.pk).update(latitud=3.44, longitud=-76.535, ubicacion_actualizada_en=AHORA)
    operador = _empleado(OPERADOR, "op@correo.com", centro)

    datos = _http(operador.usuario).get(MAPA).json()

    assert datos["sede"] == {"id": centro.pk, "nombre": "Centro", "ubicacion": {"latitud": 3.45, "longitud": -76.53}}
    assert datos["intervalo_segundos"] == 30
    assert datos["entregas"] == [{
        "pedido_id": datos["entregas"][0]["pedido_id"],
        "numero_pedido": "P-1",
        "repartidor": "Carlos Ruiz",
        "ubicacion": {"latitud": 3.44, "longitud": -76.535},
        "ubicacion_actualizada_en": "2026-11-24T15:00:00-05:00",
        "sin_senal": False,
        "destino": {"latitud": 3.43, "longitud": -76.54},
        "destino_direccion": "Calle 5 # 10-20",
        "destino_barrio": "San Fernando",
    }]


def test_ubicacion_vieja_o_ausente_es_sin_senal(centro, carlos):
    luz = _empleado(REPARTIDOR, "luz@correo.com", centro)
    _pedido(centro, "P-1", carlos)
    _pedido(centro, "P-2", luz)
    Repartidor.objects.filter(pk=carlos.pk).update(
        latitud=3.44, longitud=-76.535, ubicacion_actualizada_en=AHORA - timedelta(minutes=3)
    )
    operador = _empleado(OPERADOR, "op@correo.com", centro)

    entregas = _http(operador.usuario).get(MAPA).json()["entregas"]

    assert [(e["numero_pedido"], e["sin_senal"]) for e in entregas] == [("P-1", True), ("P-2", True)]
    assert entregas[0]["ubicacion"] is not None  # se muestra atenuada
    assert entregas[1]["ubicacion"] is None


def test_el_administrador_elige_la_sede(centro, carlos):
    sur = _sede("Sur")
    _pedido(centro, "P-1", carlos)
    _pedido(sur, "P-2", _empleado(REPARTIDOR, "otro@correo.com", sur))
    admin = Usuario.objects.create_user(username="admin@correo.com", email="admin@correo.com", password="x")
    admin.groups.add(Group.objects.get_or_create(name=ADMINISTRADOR)[0])
    api = _http(admin)

    todas = api.get(MAPA).json()
    solo_sur = api.get(MAPA, {"sede": sur.pk}).json()

    assert todas["sede"] is None and len(todas["entregas"]) == 2
    assert solo_sur["sede"]["nombre"] == "Sur"
    assert [e["numero_pedido"] for e in solo_sur["entregas"]] == ["P-2"]


def test_otros_roles_no_ven_el_mapa(centro, carlos):
    assert _http(_empleado(COCINA, "cocina@correo.com", centro).usuario).get(MAPA).status_code == 403
    assert _http(carlos.empleado.usuario).get(MAPA).status_code == 403
    assert APIClient().get(MAPA).status_code == 401
