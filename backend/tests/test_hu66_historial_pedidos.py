"""Pruebas de HU-66 · Historial completo de pedidos (SCRUM-153)."""
from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.contrib.auth.models import Group
from django.utils import timezone
from rest_framework.test import APIClient

from pedidos.estados import cambiar_estado
from pedidos.models import EstadoPedido as E
from pedidos.models import Factura, HistorialEstadoPedido, MetodoPago, Pedido
from sedes.models import Ciudad, Sede
from usuarios.models import Cliente, Empleado, Usuario
from usuarios.roles import ADMINISTRADOR, COCINA, OPERADOR, REPARTIDOR

CLIENTE = "cliente"  # los clientes no tienen grupo: se reconocen por su perfil

pytestmark = pytest.mark.django_db

LISTA = "/api/pedidos/historial/"
CLAVE = "ClaveSegura2026"


def ficha(pedido):
    return f"{LISTA}{pedido.pk}/"


# --- Datos de prueba ------------------------------------------------------------


def _sede(nombre):
    ciudad, _ = Ciudad.objects.get_or_create(nombre="Cali")
    return Sede.objects.create(
        ciudad=ciudad, nombre=nombre, direccion="Calle 1 # 2-3", latitud=3.45, longitud=-76.53,
        barrio="Centro", telefono="3000000000", correo=f"{nombre.lower().replace(' ', '')}@correo.com",
    )


@pytest.fixture
def centro():
    return _sede("Sede Centro")


@pytest.fixture
def sur():
    return _sede("Sede Sur")


def _usuario(rol, email, sede=None):
    usuario = Usuario.objects.create_user(username=email, email=email, password=CLAVE)
    if rol == CLIENTE:
        return usuario
    usuario.groups.add(Group.objects.get_or_create(name=rol)[0])
    if rol != ADMINISTRADOR:
        Empleado.objects.create(
            usuario=usuario, sede=sede, tipo_documento="CC", num_documento=email[:10],
            nombres="Nombre", apellidos="Prueba", celular="3001234567", direccion="Calle 4",
        )
    return usuario


@pytest.fixture
def admin():
    api = APIClient()
    api.force_authenticate(_usuario(ADMINISTRADOR, "admin@correo.com"))
    return api


@pytest.fixture
def laura():
    usuario = _usuario(CLIENTE, "laura@correo.com")
    return Cliente.objects.create(
        usuario=usuario, tipo_documento="CC", num_documento="1110009", nombres="Laura",
        apellidos="Gómez", celular="3109876543", fecha_nacimiento=date(2000, 1, 1),
    )


def _pedido(sede, numero, cliente=None, hace_minutos=0, estado=E.PENDIENTE_APROBACION, total=None):
    pedido = Pedido.objects.create(sede=sede, numero_pedido=numero, cliente=cliente, estado=estado)
    Pedido.objects.filter(pk=pedido.pk).update(fecha_creacion=timezone.now() - timedelta(minutes=hace_minutos))
    if total is not None:
        Factura.objects.create(
            pedido=pedido, numero=f"F-{numero}", subtotal=Decimal(total) - 5000, iva=Decimal("0"),
            costo_domicilio=Decimal("5000"), total=Decimal(total), metodo_pago=MetodoPago.EFECTIVO,
        )
    pedido.refresh_from_db()
    return pedido


# --- Criterio 1: todas las sedes, del más reciente al más antiguo, paginado ---------


def test_muestra_los_pedidos_de_todas_las_sedes_del_mas_reciente_al_mas_antiguo(admin, centro, sur):
    _pedido(centro, "P-ANTIGUO", hace_minutos=300)
    _pedido(sur, "P-RECIENTE", hace_minutos=5)
    _pedido(centro, "P-MEDIO", hace_minutos=60)

    filas = admin.get(LISTA).data["results"]

    assert [fila["numero_pedido"] for fila in filas] == ["P-RECIENTE", "P-MEDIO", "P-ANTIGUO"]
    assert {fila["sede"]["nombre"] for fila in filas} == {"Sede Centro", "Sede Sur"}


def test_cada_fila_trae_numero_fecha_sede_cliente_estado_y_total(admin, centro, laura):
    _pedido(centro, "P-1", cliente=laura, total="23000")

    fila = admin.get(LISTA).data["results"][0]

    assert fila["numero_pedido"] == "P-1"
    assert fila["fecha_creacion"]
    assert fila["sede"] == {"id": centro.pk, "nombre": "Sede Centro"}
    assert fila["cliente"] == "Laura Gómez"
    assert fila["estado"] == "pendiente_aprobacion"
    assert fila["estado_nombre"]
    assert Decimal(fila["total"]) == Decimal("23000")


def test_pedido_sin_cliente_ni_factura_no_rompe_la_lista(admin, centro):
    _pedido(centro, "P-MOSTRADOR")

    fila = admin.get(LISTA).data["results"][0]

    assert fila["cliente"] is None
    assert fila["total"] is None


def test_pagina_de_a_20_pedidos(admin, centro):
    for i in range(25):
        _pedido(centro, f"P-{i:02d}", hace_minutos=i)

    primera = admin.get(LISTA).data
    segunda = admin.get(LISTA, {"page": 2}).data

    assert primera["count"] == 25
    assert len(primera["results"]) == 20
    assert primera["next"] is not None
    assert len(segunda["results"]) == 5
    assert segunda["next"] is None
    assert primera["results"][0]["numero_pedido"] == "P-00"  # el más reciente
    assert segunda["results"][-1]["numero_pedido"] == "P-24"  # el más antiguo


def test_se_puede_cambiar_el_tamaño_de_pagina_hasta_100(admin, centro):
    for i in range(5):
        _pedido(centro, f"P-{i}")

    assert len(admin.get(LISTA, {"tamano": 2}).data["results"]) == 2
    assert admin.get(LISTA, {"tamano": 500}).data["count"] == 5  # no falla con un tamaño exagerado


def test_sin_pedidos_devuelve_una_lista_vacia(admin):
    datos = admin.get(LISTA).data

    assert datos["count"] == 0
    assert datos["results"] == []


def test_la_lista_no_hace_una_consulta_por_pedido(admin, centro, laura, django_assert_max_num_queries):
    for i in range(15):
        _pedido(centro, f"P-{i}", cliente=laura, total="20000")

    with django_assert_max_num_queries(6):
        assert admin.get(LISTA).status_code == 200


# --- Criterio 2: ficha técnica con marcas de tiempo ----------------------------------


def test_la_ficha_trae_cada_cambio_de_estado_con_su_hora_y_usuario(admin, centro):
    operador = _usuario(OPERADOR, "operador@correo.com", centro)
    cocina = _usuario(COCINA, "cocina@correo.com", centro)
    pedido = _pedido(centro, "P-1", total="30000")
    pedido = cambiar_estado(pedido, E.RECIBIDO, operador, OPERADOR)
    pedido = cambiar_estado(pedido, E.EN_PREPARACION, cocina, COCINA)

    datos = admin.get(ficha(pedido)).data

    pasos = datos["historial"]
    assert [paso["estado"] for paso in pasos][-2:] == ["recibido", "en_preparacion"]
    assert all(paso["fecha_hora"] for paso in pasos)
    assert pasos[-2]["usuario"] == "operador@correo.com"
    assert pasos[-1]["usuario"] == "cocina@correo.com"


def test_la_ficha_calcula_los_minutos_entre_pasos(admin, centro):
    pedido = _pedido(centro, "P-1")
    inicio = timezone.now() - timedelta(minutes=30)
    primero = HistorialEstadoPedido.objects.create(pedido=pedido, estado=E.RECIBIDO)
    segundo = HistorialEstadoPedido.objects.create(pedido=pedido, estado=E.EN_PREPARACION)
    HistorialEstadoPedido.objects.filter(pk=primero.pk).update(fecha_hora=inicio)
    HistorialEstadoPedido.objects.filter(pk=segundo.pk).update(fecha_hora=inicio + timedelta(minutes=12))

    pasos = admin.get(ficha(pedido)).data["historial"]

    assert pasos[0]["minutos_desde_anterior"] is None
    assert pasos[1]["minutos_desde_anterior"] == 12


def test_un_pedido_cancelado_muestra_el_motivo(admin, centro):
    operador = _usuario(OPERADOR, "operador@correo.com", centro)
    pedido = _pedido(centro, "P-1")
    pedido = cambiar_estado(pedido, E.CANCELADO, operador, OPERADOR, "El cliente no respondió")

    datos = admin.get(ficha(pedido)).data

    assert datos["estado"] == "cancelado"
    assert datos["motivo_cancelacion"] == "El cliente no respondió"
    assert datos["historial"][-1]["observacion"] == "El cliente no respondió"


def test_la_ficha_trae_la_factura_y_los_datos_de_entrega(admin, centro, laura):
    pedido = _pedido(centro, "P-1", cliente=laura, total="23000")
    Pedido.objects.filter(pk=pedido.pk).update(entrega_direccion="Calle 9 # 4-50", entrega_barrio="San Antonio")

    datos = admin.get(ficha(pedido)).data

    assert datos["factura"]["metodo_pago"] == "efectivo"
    assert Decimal(datos["factura"]["costo_domicilio"]) == Decimal("5000")
    assert datos["entrega_direccion"] == "Calle 9 # 4-50"
    assert datos["repartidor"] is None
    assert datos["detalles"] == []


def test_ficha_de_un_pedido_que_no_existe(admin):
    assert admin.get(f"{LISTA}999999/").status_code == 404


# --- Criterio 3: solo el administrador -----------------------------------------------


@pytest.mark.parametrize("rol", [OPERADOR, COCINA, REPARTIDOR, CLIENTE])
def test_otros_roles_no_pueden_ver_el_historial(centro, rol):
    pedido = _pedido(centro, "P-1")
    api = APIClient()
    api.force_authenticate(_usuario(rol, f"{rol}@correo.com", centro))

    assert api.get(LISTA).status_code == 403
    assert api.get(ficha(pedido)).status_code == 403


def test_sin_sesion_no_se_puede_ver(centro):
    pedido = _pedido(centro, "P-1")

    assert APIClient().get(LISTA).status_code == 401
    assert APIClient().get(ficha(pedido)).status_code == 401
