from datetime import date
from decimal import Decimal
from types import SimpleNamespace

import pytest
from django.contrib.auth.models import Group
from django.db import IntegrityError, transaction
from rest_framework.test import APIClient

from menu.models import CategoriaMenu, Producto
from pedidos.models import Pedido
from sedes.models import Ciudad, Sede, ZonaCobertura
from usuarios.models import Cliente, DireccionEntrega, Usuario

URL = "/api/zonas-cobertura/"
CONFIRMAR = "/api/pedidos/confirmar/"
pytestmark = pytest.mark.django_db


def _usuario(email, rol=None):
    usuario = Usuario.objects.create_user(username=email, email=email, password="ClaveSegura2026")
    if rol:
        usuario.groups.add(Group.objects.get_or_create(name=rol)[0])
    return usuario


def _http(usuario):
    c = APIClient()
    c.force_authenticate(user=usuario)
    return c


@pytest.fixture
def m(db):
    ciudad = Ciudad.objects.create(nombre="Cali")
    sede = Sede.objects.create(
        ciudad=ciudad, nombre="Norte", direccion="Calle 1 # 2-3", latitud=3.45,
        longitud=-76.53, barrio="Granada", telefono="3000000000", correo="s@correo.com",
    )
    zona = ZonaCobertura.objects.create(
        sede=sede, nombre="Zona 1", radio=5, centro_latitud=3.45, centro_longitud=-76.53,
        tarifa_domicilio=Decimal("3000"), tiempo_estimado=40, pedido_minimo=Decimal("10000"),
    )
    usuario_cliente = _usuario("cli@correo.com")
    cliente = Cliente.objects.create(
        usuario=usuario_cliente, tipo_documento="CC", num_documento="123", nombres="Ana",
        apellidos="Prueba", celular="3001234567", fecha_nacimiento=date(2000, 1, 1),
    )
    direccion = DireccionEntrega.objects.create(
        ciudad=ciudad, cliente=cliente, direccion="Calle 5 # 6-7", latitud=3.46, longitud=-76.53
    )
    categoria = CategoriaMenu.objects.create(nombre="Platos")
    producto = Producto.objects.create(
        categoria=categoria, nombre="Hamburguesa", precio_base=Decimal("20000"),
        tiempo_preparacion=15,
    )
    return SimpleNamespace(
        sede=sede, zona=zona, usuario_cliente=usuario_cliente, direccion=direccion,
        producto=producto,
    )


@pytest.fixture
def admin():
    return _http(_usuario("admin@correo.com", "administrador"))


def _confirmar(m):
    cuerpo = {
        "sede_id": m.sede.pk,
        "direccion_id": m.direccion.pk,
        "metodo_pago": "tarjeta",
        "items": [{"producto_id": m.producto.pk, "cantidad": 1}],
    }
    return _http(m.usuario_cliente).post(CONFIRMAR, cuerpo, format="json")


def _zona_sin_configurar(m, **extra):
    return ZonaCobertura.objects.create(
        sede=m.sede, nombre="Sin configurar", radio=1, centro_latitud=3.60,
        centro_longitud=-76.53, pedido_minimo=Decimal("10000"), activo=False, **extra,
    )


def _cuerpo_sin_tarifa(m, **extra):
    return {
        "sede": m.sede.pk, "nombre": "Zona X", "radio": 1, "centro_latitud": 3.60,
        "centro_longitud": -76.53, "pedido_minimo": "10000", **extra,
    }


# --- Criterio 3: costos históricos (integración con HU-23) ------------------

def test_pedido_previo_conserva_tarifa_y_tiempo_y_el_nuevo_usa_los_nuevos(m, admin):
    r1 = _confirmar(m)
    assert r1.status_code == 201

    r = admin.patch(
        f"{URL}{m.zona.pk}/", {"tarifa_domicilio": "5000", "tiempo_estimado": 60}, format="json"
    )
    assert r.status_code == 200

    r2 = _confirmar(m)
    assert r2.status_code == 201

    antes = Pedido.objects.get(numero_pedido=r1.data["numero_pedido"])
    despues = Pedido.objects.get(numero_pedido=r2.data["numero_pedido"])
    assert antes.tiempo_estimado_entrega == 40
    assert antes.factura.costo_domicilio == Decimal("3000")
    assert despues.tiempo_estimado_entrega == 60
    assert despues.factura.costo_domicilio == Decimal("5000")
    # Mismo pedido, solo cambió el domicilio: el total sube exactamente 2000.
    assert despues.factura.total - antes.factura.total == Decimal("2000")


def test_zona_desactivada_no_recibe_pedidos_nuevos_pero_los_previos_se_conservan(m, admin):
    assert _confirmar(m).status_code == 201
    assert admin.patch(f"{URL}{m.zona.pk}/", {"activo": False}, format="json").status_code == 200

    assert _confirmar(m).status_code == 400
    pedido = Pedido.objects.get()
    assert pedido.zona_cobertura == m.zona
    assert pedido.factura.costo_domicilio == Decimal("3000")


# --- Criterios 1 y 2: validaciones -----------------------------------------

def test_tarifa_cero_es_valida(m, admin):
    r = admin.patch(f"{URL}{m.zona.pk}/", {"tarifa_domicilio": "0"}, format="json")
    assert r.status_code == 200
    m.zona.refresh_from_db()
    assert m.zona.tarifa_domicilio == 0


@pytest.mark.parametrize(
    "campo,valor",
    [
        ("tarifa_domicilio", "abc"),
        ("tarifa_domicilio", "12abc"),
        ("tarifa_domicilio", "-1"),
        ("tiempo_estimado", "abc"),
        ("tiempo_estimado", 0),
        ("tiempo_estimado", -5),
    ],
)
def test_valores_invalidos_son_rechazados_y_no_se_guardan(m, admin, campo, valor):
    r = admin.patch(f"{URL}{m.zona.pk}/", {campo: valor}, format="json")
    assert r.status_code == 400
    assert campo in r.data
    m.zona.refresh_from_db()
    assert m.zona.tarifa_domicilio == Decimal("3000")
    assert m.zona.tiempo_estimado == 40


def test_nulos_con_la_zona_activa_son_rechazados(m, admin):
    r = admin.patch(
        f"{URL}{m.zona.pk}/", {"tarifa_domicilio": None, "activo": True}, format="json"
    )
    assert r.status_code == 400
    assert "activo" in r.data
    m.zona.refresh_from_db()
    assert m.zona.tarifa_domicilio == Decimal("3000")


# --- Criterio 4: sin tarifa ni tiempo, desactivada --------------------------

def test_zona_sin_tarifa_ni_tiempo_se_crea_desactivada(m, admin):
    r = admin.post(URL, _cuerpo_sin_tarifa(m), format="json")
    assert r.status_code == 201
    assert r.data["activo"] is False
    assert r.data["tarifa_domicilio"] is None and r.data["tiempo_estimado"] is None


@pytest.mark.parametrize(
    "extra", [{}, {"tarifa_domicilio": "3000"}, {"tiempo_estimado": 40}]
)
def test_no_se_puede_crear_activa_si_falta_tarifa_o_tiempo(m, admin, extra):
    r = admin.post(URL, _cuerpo_sin_tarifa(m, activo=True, **extra), format="json")
    assert r.status_code == 400
    assert "activo" in r.data
    assert ZonaCobertura.objects.count() == 1  # solo la del fixture


def test_zona_sin_configurar_no_se_activa_hasta_tener_tarifa_y_tiempo(m, admin):
    zona = _zona_sin_configurar(m)
    assert admin.patch(f"{URL}{zona.pk}/", {"activo": True}, format="json").status_code == 400

    r = admin.patch(
        f"{URL}{zona.pk}/",
        {"tarifa_domicilio": "2500", "tiempo_estimado": 30, "activo": True},
        format="json",
    )
    assert r.status_code == 200
    assert r.data["activo"] is True


def test_vaciar_la_tarifa_de_una_zona_activa_la_desactiva(m, admin):
    r = admin.patch(f"{URL}{m.zona.pk}/", {"tarifa_domicilio": None}, format="json")
    assert r.status_code == 200
    assert r.data["activo"] is False
    m.zona.refresh_from_db()
    assert m.zona.activo is False and m.zona.tarifa_domicilio is None


def test_la_base_impide_una_zona_activa_sin_tarifa(m):
    with pytest.raises(IntegrityError), transaction.atomic():
        ZonaCobertura.objects.create(
            sede=m.sede, nombre="Rota", radio=1, centro_latitud=3.60, centro_longitud=-76.53,
            pedido_minimo=Decimal("10000"), tiempo_estimado=30, activo=True,
        )