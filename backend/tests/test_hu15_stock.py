from datetime import date
from decimal import Decimal
from types import SimpleNamespace

import pytest
from rest_framework.test import APIClient

from inventario.models import InventarioInsumo, InventarioProducto
from menu.models import CategoriaMenu, Insumo, Producto, ProductoInsumo
from pedidos import servicios
from pedidos.models import Pedido
from sedes.models import Ciudad, Sede, ZonaCobertura
from usuarios.models import Cliente, DireccionEntrega, Usuario

URL = "/api/pedidos/confirmar/"
pytestmark = pytest.mark.django_db


@pytest.fixture
def m(db):
    ciudad = Ciudad.objects.create(nombre="Cali")
    sede = Sede.objects.create(
        ciudad=ciudad, nombre="Norte", direccion="Calle 1 # 2-3", latitud=3.45,
        longitud=-76.53, barrio="Granada", telefono="3000000000", correo="s@correo.com",
    )
    ZonaCobertura.objects.create(
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
        ciudad=ciudad, cliente=cliente, direccion="Calle 5 # 6-7", latitud=3.46, longitud=-76.53,
    )
    categoria = CategoriaMenu.objects.create(nombre="Platos")
    producto = Producto.objects.create(
        categoria=categoria, nombre="Hamburguesa", precio_base=Decimal("20000"),
        tiempo_preparacion=15,
    )
    return SimpleNamespace(sede=sede, usuario=usuario, direccion=direccion, producto=producto)


@pytest.fixture
def client(m):
    c = APIClient()
    c.force_authenticate(user=m.usuario)
    return c


def _body(m, cantidad=1, **item_extra):
    return {
        "sede_id": m.sede.pk,
        "direccion_id": m.direccion.pk,
        "metodo_pago": "tarjeta",
        "items": [{"producto_id": m.producto.pk, "cantidad": cantidad, **item_extra}],
    }


def _con_stock_de_producto(m, stock):
    m.producto.tipo_control_stock = Producto.TipoControlStock.PRODUCTO
    m.producto.save()
    return InventarioProducto.objects.create(sede=m.sede, producto=m.producto, stock_actual=stock)


def test_descuenta_stock_de_producto_terminado(client, m):
    inv = _con_stock_de_producto(m, 5)
    assert client.post(URL, _body(m, cantidad=2), format="json").status_code == 201
    inv.refresh_from_db()
    assert inv.stock_actual == 3
    assert inv.disponible is True


def test_al_llegar_a_cero_queda_no_disponible_y_se_bloquea(client, m):
    inv = _con_stock_de_producto(m, 2)
    assert client.post(URL, _body(m, cantidad=2), format="json").status_code == 201
    inv.refresh_from_db()
    assert inv.stock_actual == 0
    assert inv.disponible is False

    r = client.post(URL, _body(m, cantidad=1), format="json")
    assert r.status_code == 400
    assert "agotado" in r.data["items"][0]["motivo"].lower()
    assert Pedido.objects.count() == 1


def test_descuenta_insumos_de_la_receta_sin_los_excluidos(client, m):
    m.producto.tipo_control_stock = Producto.TipoControlStock.INSUMOS
    m.producto.save()
    carne = Insumo.objects.create(nombre="Carne", unidad_medida="kg")
    cebolla = Insumo.objects.create(nombre="Cebolla", unidad_medida="kg")
    ProductoInsumo.objects.create(
        producto=m.producto, insumo=carne, cantidad_necesaria=Decimal("0.2")
    )
    ProductoInsumo.objects.create(
        producto=m.producto, insumo=cebolla, cantidad_necesaria=Decimal("0.1"), es_excluible=True
    )
    inv_carne = InventarioInsumo.objects.create(sede=m.sede, insumo=carne, stock_actual=Decimal("1"))
    inv_cebolla = InventarioInsumo.objects.create(sede=m.sede, insumo=cebolla, stock_actual=Decimal("1"))

    r = client.post(URL, _body(m, cantidad=2, exclusiones=[cebolla.pk]), format="json")

    assert r.status_code == 201
    inv_carne.refresh_from_db()
    inv_cebolla.refresh_from_db()
    assert inv_carne.stock_actual == Decimal("0.600")
    assert inv_cebolla.stock_actual == Decimal("1.000")  # excluida: no se descuenta


def test_insumo_en_cero_queda_no_disponible(client, m):
    m.producto.tipo_control_stock = Producto.TipoControlStock.INSUMOS
    m.producto.save()
    carne = Insumo.objects.create(nombre="Carne", unidad_medida="kg")
    ProductoInsumo.objects.create(
        producto=m.producto, insumo=carne, cantidad_necesaria=Decimal("0.5")
    )
    inv = InventarioInsumo.objects.create(sede=m.sede, insumo=carne, stock_actual=Decimal("1"))

    assert client.post(URL, _body(m, cantidad=2), format="json").status_code == 201
    inv.refresh_from_db()
    assert inv.stock_actual == 0
    assert inv.disponible is False
    assert client.post(URL, _body(m), format="json").status_code == 400


def test_sin_control_de_stock_no_toca_inventario(client, m):
    inv = InventarioProducto.objects.create(sede=m.sede, producto=m.producto, stock_actual=5)
    assert client.post(URL, _body(m, cantidad=2), format="json").status_code == 201
    inv.refresh_from_db()
    assert inv.stock_actual == 5


def test_si_el_pedido_falla_el_stock_no_se_descuenta(client, m, monkeypatch):
    inv = _con_stock_de_producto(m, 5)

    def falla(*args, **kwargs):
        raise RuntimeError("fallo simulado")

    monkeypatch.setattr(servicios, "_crear_notificacion", falla)
    with pytest.raises(RuntimeError):
        client.post(URL, _body(m, cantidad=2), format="json")
    inv.refresh_from_db()
    assert inv.stock_actual == 5
    assert inv.disponible is True