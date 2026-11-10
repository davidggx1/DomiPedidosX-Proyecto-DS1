"""Pruebas de HU-44 · Dirección del cliente en el mapa (SCRUM-113)."""
import pytest
from django.contrib.auth.models import Group
from rest_framework.test import APIClient

from pedidos.models import EstadoPedido as E
from pedidos.models import Pedido
from sedes.models import Ciudad, Sede
from usuarios.models import Empleado, Repartidor, Usuario
from usuarios.roles import REPARTIDOR

pytestmark = pytest.mark.django_db

MIS_ENTREGAS = "/api/pedidos/mis-entregas/"
CLAVE = "ClaveSegura2026"


def url_detalle(pedido):
    return f"{MIS_ENTREGAS}{pedido.id}/"


# --- Datos de prueba ------------------------------------------------------------


@pytest.fixture
def centro():
    ciudad = Ciudad.objects.create(nombre="Cali")
    return Sede.objects.create(
        ciudad=ciudad, nombre="Sede Centro", direccion="Calle 1 # 2-3", latitud=3.45,
        longitud=-76.53, barrio="Centro", telefono="3000000000", correo="centro@correo.com",
    )


def crear_repartidor(email, sede):
    usuario = Usuario.objects.create_user(username=email, email=email, password=CLAVE)
    usuario.groups.add(Group.objects.get_or_create(name=REPARTIDOR)[0])
    empleado = Empleado.objects.create(
        usuario=usuario, sede=sede, tipo_documento="CC", num_documento=email[:10],
        nombres="Nombre", apellidos="Prueba", celular="3001234567", direccion="Calle 4",
    )
    return usuario, Repartidor.objects.create(empleado=empleado, disponible=True)


@pytest.fixture
def ana(centro):
    return crear_repartidor("ana@correo.com", centro)


def crear_pedido(sede, repartidor, numero="P-1", **extra):
    datos = {
        "entrega_direccion": "Carrera 10 # 20-30",
        "entrega_barrio": "San Fernando",
        "entrega_latitud": 3.4372,
        "entrega_longitud": -76.5447,
    }
    datos.update(extra)
    return Pedido.objects.create(
        sede=sede, numero_pedido=numero, estado=E.LISTO_DESPACHO, repartidor=repartidor, **datos
    )


def detalle(usuario, pedido):
    api = APIClient()
    api.force_authenticate(usuario)
    return api.get(url_detalle(pedido))


# --- Criterio 1: el mapa recibe las coordenadas del cliente --------------------


def test_detalle_trae_las_coordenadas_para_el_pin(ana, centro):
    usuario, repartidor = ana
    pedido = crear_pedido(centro, repartidor)

    datos = detalle(usuario, pedido).data

    assert datos["tiene_ubicacion"] is True
    assert datos["entrega_latitud"] == pytest.approx(3.4372)
    assert datos["entrega_longitud"] == pytest.approx(-76.5447)


# --- Criterio 2: punto de partida de la ruta cuando no hay GPS -----------------


def test_detalle_trae_la_sede_como_punto_de_recogida(ana, centro):
    usuario, repartidor = ana
    pedido = crear_pedido(centro, repartidor)

    recogida = detalle(usuario, pedido).data["punto_recogida"]

    assert recogida["nombre"] == "Sede Centro"
    assert recogida["direccion"] == "Calle 1 # 2-3"
    assert recogida["latitud"] == pytest.approx(3.45)
    assert recogida["longitud"] == pytest.approx(-76.53)


# --- Criterio 3: la dirección escrita siempre está disponible ------------------


def test_direccion_completa_en_texto_con_barrio_y_ciudad(ana, centro):
    usuario, repartidor = ana
    pedido = crear_pedido(centro, repartidor)

    assert detalle(usuario, pedido).data["direccion_completa"] == (
        "Carrera 10 # 20-30, San Fernando, Cali"
    )


def test_sin_coordenadas_el_detalle_avisa_y_conserva_el_texto(ana, centro):
    usuario, repartidor = ana
    pedido = crear_pedido(
        centro, repartidor, entrega_latitud=None, entrega_longitud=None, entrega_barrio=""
    )

    datos = detalle(usuario, pedido).data

    assert datos["tiene_ubicacion"] is False
    assert datos["direccion_completa"] == "Carrera 10 # 20-30, Cali"


# --- Privacidad: la ubicación del cliente solo la ve su repartidor -------------


def test_otro_repartidor_no_ve_la_ubicacion(ana, centro):
    _, repartidor = ana
    otro_usuario, _ = crear_repartidor("luis@correo.com", centro)
    pedido = crear_pedido(centro, repartidor)

    assert detalle(otro_usuario, pedido).status_code == 404
