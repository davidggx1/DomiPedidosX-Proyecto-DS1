"""HU-39 · La comanda de cocina muestra el repartidor asignado y cuándo llega a la sede."""
from datetime import datetime

import pytest
from django.contrib.auth.models import Group
from django.utils import timezone
from rest_framework.test import APIClient

from pedidos.asignacion import asignar, retirar
from pedidos.models import EstadoPedido as E, OrigenPedido, Pedido
from sedes.models import Ciudad, Sede
from usuarios.models import Empleado, Repartidor, Usuario
from usuarios.roles import COCINA, REPARTIDOR

pytestmark = pytest.mark.django_db

TABLERO = "/api/pedidos/cocina/tablero/"


def llegada(pedido):
    return f"/api/pedidos/mis-entregas/{pedido.pk}/llegada/"


@pytest.fixture
def sede():
    ciudad, _ = Ciudad.objects.get_or_create(nombre="Cali")
    return Sede.objects.create(
        ciudad=ciudad, nombre="Centro", direccion="Calle 1 # 2-3", latitud=3.45, longitud=-76.53,
        barrio="Granada", telefono="3000000000", correo="s@correo.com",
    )


def _empleado(rol, email, sede, nombres="N", apellidos="A"):
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


def _pedido(sede, numero="P-1", estado=E.LISTO_DESPACHO, repartidor=None, origen=OrigenPedido.WEB):
    return Pedido.objects.create(
        sede=sede, numero_pedido=numero, estado=estado, repartidor=repartidor, origen=origen
    )


def _tarjeta(cocina, pedido):
    tablero = _http(cocina.usuario).get(TABLERO).json()
    return next(t for columna in tablero.values() for t in columna if t["id"] == pedido.pk)


@pytest.fixture
def carlos(sede):
    return _empleado(REPARTIDOR, "carlos@correo.com", sede, "Carlos", "Ruiz")


@pytest.fixture
def cocina(sede):
    return _empleado(COCINA, "cocina@correo.com", sede)


def test_la_comanda_muestra_el_repartidor_y_que_aun_no_llega(sede, carlos, cocina):
    pedido = _pedido(sede, repartidor=carlos)

    tarjeta = _tarjeta(cocina, pedido)

    assert tarjeta["lleva_domicilio"] is True
    assert tarjeta["repartidor"] == "Carlos Ruiz"
    assert tarjeta["repartidor_llego_en"] is None


def test_el_repartidor_avisa_que_llego_y_cocina_lo_ve(sede, carlos, cocina, monkeypatch):
    ahora = timezone.make_aware(datetime(2026, 11, 24, 12, 30))
    monkeypatch.setattr(timezone, "now", lambda: ahora)
    pedido = _pedido(sede, repartidor=carlos)

    respuesta = _http(carlos.empleado.usuario).post(llegada(pedido))

    assert respuesta.status_code == 200, respuesta.data
    assert respuesta.data["repartidor_llego_en"] is not None
    pedido.refresh_from_db()
    assert pedido.repartidor_llego_en == ahora
    assert _tarjeta(cocina, pedido)["repartidor_llego_en"] is not None


def test_avisar_dos_veces_no_cambia_la_hora(sede, carlos):
    pedido = _pedido(sede, repartidor=carlos)
    api = _http(carlos.empleado.usuario)
    api.post(llegada(pedido))
    primera = Pedido.objects.get(pk=pedido.pk).repartidor_llego_en

    api.post(llegada(pedido))

    assert Pedido.objects.get(pk=pedido.pk).repartidor_llego_en == primera


def test_solo_antes_de_recoger(sede, carlos):
    pedido = _pedido(sede, estado=E.RECOGIDO, repartidor=carlos)

    respuesta = _http(carlos.empleado.usuario).post(llegada(pedido))

    assert respuesta.status_code == 409
    assert "antes de recoger" in respuesta.data["detail"]


def test_solo_el_repartidor_asignado(sede, carlos, cocina):
    otro = _empleado(REPARTIDOR, "otro@correo.com", sede)
    pedido = _pedido(sede, repartidor=carlos)

    assert _http(otro.empleado.usuario).post(llegada(pedido)).status_code == 404
    assert _http(cocina.usuario).post(llegada(pedido)).status_code == 403
    assert APIClient().post(llegada(pedido)).status_code == 401


def test_cambiar_de_repartidor_borra_la_llegada(sede, carlos, cocina):
    pedido = _pedido(sede, repartidor=carlos)
    _http(carlos.empleado.usuario).post(llegada(pedido))

    retirar(pedido)
    pedido.refresh_from_db()
    assert pedido.repartidor_llego_en is None

    nuevo = _empleado(REPARTIDOR, "nuevo@correo.com", sede, "Luz", "Mora")
    asignar(pedido, nuevo)
    tarjeta = _tarjeta(cocina, pedido)
    assert (tarjeta["repartidor"], tarjeta["repartidor_llego_en"]) == ("Luz Mora", None)


def test_pedido_de_mostrador_no_lleva_repartidor(sede, cocina):
    pedido = _pedido(sede, origen=OrigenPedido.MOSTRADOR)

    tarjeta = _tarjeta(cocina, pedido)

    assert tarjeta["lleva_domicilio"] is False and tarjeta["repartidor"] is None


def test_el_repartidor_ve_su_aviso_en_mis_entregas(sede, carlos):
    pedido = _pedido(sede, repartidor=carlos)
    api = _http(carlos.empleado.usuario)
    api.post(llegada(pedido))

    entrega = api.get("/api/pedidos/mis-entregas/").json()[0]

    assert entrega["repartidor_llego_en"] is not None
