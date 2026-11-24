"""HU-49 · El cliente ve dónde va el repartidor de su pedido mientras está en camino."""
from datetime import date, datetime, timedelta

import pytest
from django.contrib.auth.models import Group
from django.utils import timezone
from rest_framework.test import APIClient

from pedidos.models import EstadoPedido as E, Pedido
from sedes.models import Ciudad, Sede
from usuarios.models import Cliente, Empleado, Repartidor, Usuario
from usuarios.roles import OPERADOR, REPARTIDOR

pytestmark = pytest.mark.django_db

AHORA = timezone.make_aware(datetime(2026, 11, 24, 15, 0))


@pytest.fixture(autouse=True)
def reloj(monkeypatch):
    monkeypatch.setattr(timezone, "now", lambda: AHORA)


def _url(pedido):
    return f"/api/pedidos/mios/{pedido.pk}/ubicacion/"


@pytest.fixture
def sede():
    ciudad, _ = Ciudad.objects.get_or_create(nombre="Cali")
    return Sede.objects.create(
        ciudad=ciudad, nombre="Centro", direccion="Calle 1 # 2-3", latitud=3.45, longitud=-76.53,
        barrio="Granada", telefono="3000000000", correo="centro@correo.com",
    )


def _cliente(email, documento):
    usuario = Usuario.objects.create_user(username=email, email=email, password="x")
    return Cliente.objects.create(
        usuario=usuario, tipo_documento="CC", num_documento=documento, nombres="Ana", apellidos="Gómez",
        celular=f"300{documento}", fecha_nacimiento=date(2000, 1, 1),
    )


@pytest.fixture
def ana():
    return _cliente("ana@correo.com", "1010101")


@pytest.fixture
def carlos(sede):
    usuario = Usuario.objects.create_user(username="carlos@correo.com", email="carlos@correo.com", password="x")
    usuario.groups.add(Group.objects.get_or_create(name=REPARTIDOR)[0])
    empleado = Empleado.objects.create(
        usuario=usuario, sede=sede, tipo_documento="CC", num_documento="2020", nombres="Carlos Andrés",
        apellidos="Ruiz", celular="3001234567", direccion="Calle 4",
    )
    return Repartidor.objects.create(
        empleado=empleado, disponible=False, latitud=3.44, longitud=-76.535, ubicacion_actualizada_en=AHORA,
    )


def _pedido(sede, cliente, repartidor, estado=E.EN_CAMINO, numero="P-1"):
    return Pedido.objects.create(
        sede=sede, cliente=cliente, numero_pedido=numero, estado=estado, repartidor=repartidor,
        entrega_direccion="Calle 5 # 10-20", entrega_barrio="San Fernando",
        entrega_latitud=3.43, entrega_longitud=-76.54,
    )


def _http(cliente):
    api = APIClient()
    api.force_authenticate(cliente.usuario)
    return api


def test_en_camino_ve_al_repartidor_y_su_destino(sede, ana, carlos):
    pedido = _pedido(sede, ana, carlos)

    datos = _http(ana).get(_url(pedido)).json()

    assert datos == {
        "estado": "en_camino",
        "rastreando": True,
        "intervalo_segundos": 30,
        "repartidor": "Carlos",
        "ubicacion": {"latitud": 3.44, "longitud": -76.535},
        "ubicacion_actualizada_en": "2026-11-24T15:00:00-05:00",
        "sin_senal": False,
        "destino": {"latitud": 3.43, "longitud": -76.54},
    }


def test_ubicacion_vieja_es_sin_senal(sede, ana, carlos):
    Repartidor.objects.filter(pk=carlos.pk).update(ubicacion_actualizada_en=AHORA - timedelta(minutes=5))
    pedido = _pedido(sede, ana, carlos)

    datos = _http(ana).get(_url(pedido)).json()

    assert datos["sin_senal"] is True and datos["ubicacion"] is not None


def test_en_camino_sin_ubicacion_todavia(sede, ana, carlos):
    Repartidor.objects.filter(pk=carlos.pk).update(ubicacion_actualizada_en=None)
    pedido = _pedido(sede, ana, carlos)

    datos = _http(ana).get(_url(pedido)).json()

    assert (datos["rastreando"], datos["ubicacion"], datos["sin_senal"]) == (True, None, True)


@pytest.mark.parametrize("estado", [E.EN_PREPARACION, E.LISTO_DESPACHO, E.RECOGIDO, E.ENTREGADO, E.CANCELADO])
def test_fuera_de_en_camino_no_se_expone_la_ubicacion(sede, ana, carlos, estado):
    pedido = _pedido(sede, ana, carlos, estado=estado)

    datos = _http(ana).get(_url(pedido)).json()

    assert datos["estado"] == estado
    assert datos["rastreando"] is False
    assert (datos["repartidor"], datos["ubicacion"], datos["destino"]) == (None, None, None)


def test_no_ve_pedidos_de_otro_cliente(sede, ana, carlos):
    pedido = _pedido(sede, _cliente("otro@correo.com", "3030303"), carlos)

    assert _http(ana).get(_url(pedido)).status_code == 404


def test_solo_clientes(sede, ana, carlos):
    pedido = _pedido(sede, ana, carlos)
    usuario = Usuario.objects.create_user(username="op@correo.com", email="op@correo.com", password="x")
    usuario.groups.add(Group.objects.get_or_create(name=OPERADOR)[0])
    api = APIClient()
    api.force_authenticate(usuario)

    assert api.get(_url(pedido)).status_code == 403
    assert _http_repartidor(carlos).get(_url(pedido)).status_code == 403
    assert APIClient().get(_url(pedido)).status_code == 401


def _http_repartidor(repartidor):
    api = APIClient()
    api.force_authenticate(repartidor.empleado.usuario)
    return api
