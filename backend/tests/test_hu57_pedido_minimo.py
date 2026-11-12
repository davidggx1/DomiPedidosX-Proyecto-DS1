from datetime import date
from decimal import Decimal
from types import SimpleNamespace

import pytest
from rest_framework.test import APIClient

from menu.models import CategoriaMenu, Producto
from pedidos.models import Pedido
from sedes.models import Ciudad, Sede, ZonaCobertura
from usuarios.models import Cliente, DireccionEntrega, Usuario

CONFIRMAR = "/api/pedidos/confirmar/"
COBERTURA = "/api/sedes/validar-cobertura/"
pytestmark = pytest.mark.django_db


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
    usuario = Usuario.objects.create_user(
        username="cli@correo.com", email="cli@correo.com", password="ClaveSegura2026"
    )
    cliente = Cliente.objects.create(
        usuario=usuario, tipo_documento="CC", num_documento="123", nombres="Ana",
        apellidos="Prueba", celular="3001234567", fecha_nacimiento=date(2000, 1, 1),
    )
    direccion = DireccionEntrega.objects.create(
        ciudad=ciudad, cliente=cliente, direccion="Calle 5 # 6-7", latitud=3.46, longitud=-76.53
    )
    categoria = CategoriaMenu.objects.create(nombre="Platos")
    producto = Producto.objects.create(
        categoria=categoria, nombre="Hamburguesa", precio_base=Decimal("5000"),
        tiempo_preparacion=15,
    )
    client = APIClient()
    client.force_authenticate(user=usuario)
    return SimpleNamespace(
        sede=sede, zona=zona, direccion=direccion, producto=producto, client=client
    )


def _confirmar(m, cantidad=1):
    cuerpo = {
        "sede_id": m.sede.pk,
        "direccion_id": m.direccion.pk,
        "metodo_pago": "tarjeta",
        "items": [{"producto_id": m.producto.pk, "cantidad": cantidad}],
    }
    return m.client.post(CONFIRMAR, cuerpo, format="json")


def test_bajo_el_minimo_se_rechaza_e_informa_cuanto_falta(m):
    r = _confirmar(m)  # subtotal 5000, mínimo 10000
    assert r.status_code == 400
    assert Decimal(r.data["faltante"]) == Decimal("5000")
    assert Decimal(r.data["pedido_minimo"]) == Decimal("10000")
    assert "5,000" in r.data["detail"]
    assert not Pedido.objects.exists()


def test_igual_al_minimo_se_acepta(m):
    assert _confirmar(m, cantidad=2).status_code == 201  # 2 x 5000 = 10000


def test_sobre_el_minimo_se_acepta(m):
    assert _confirmar(m, cantidad=3).status_code == 201


def test_minimo_cero_equivale_a_sin_minimo(m):
    m.zona.pedido_minimo = Decimal("0")
    m.zona.save()
    assert _confirmar(m).status_code == 201


def test_el_domicilio_no_cuenta_para_el_minimo(m):
    # Subtotal 5000 + domicilio 3000 = 8000; con mínimo 7000 el total lo superaría,
    # pero el subtotal no, así que debe rechazarse.
    m.zona.pedido_minimo = Decimal("7000")
    m.zona.save()
    r = _confirmar(m)
    assert r.status_code == 400
    assert Decimal(r.data["faltante"]) == Decimal("2000")


def test_la_cobertura_informa_el_pedido_minimo(m):
    r = APIClient().post(COBERTURA, {"latitud": 3.46, "longitud": -76.53}, format="json")
    assert r.status_code == 200
    assert r.data["cubierto"] is True
    assert r.data["sede"]["pedido_minimo"] == 10000.0