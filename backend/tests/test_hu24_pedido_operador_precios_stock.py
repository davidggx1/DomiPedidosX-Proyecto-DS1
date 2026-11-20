"""HU-24 fix: operator orders follow the same price and stock rules as the web.

Before: a size crashed (tamano.precio does not exist), line subtotals left out
add-ons and stock was never decremented, so cancelling over-restored it.
"""
from decimal import Decimal
from types import SimpleNamespace

import pytest
from django.contrib.auth.models import Group
from rest_framework.test import APIClient

from inventario.models import InventarioInsumo, InventarioProducto
from menu.models import Adicion, CategoriaMenu, Insumo, Producto, ProductoAdicion, ProductoTamano
from pedidos.models import DetallePedido, EstadoPedido, HistorialEstadoPedido, Pedido
from sedes.models import Ciudad, Sede
from usuarios.models import Empleado, Usuario

pytestmark = pytest.mark.django_db

URL = "/api/pedidos/operador/crear/"


@pytest.fixture
def m(db):
    sede = Sede.objects.create(
        ciudad=Ciudad.objects.create(nombre="Cali"), nombre="Norte",
        direccion="Calle 1 # 2-3", latitud=3.45, longitud=-76.53, barrio="Granada",
        telefono="3000000000", correo="s@correo.com",
    )
    usuario = Usuario.objects.create_user(
        username="op@correo.com", email="op@correo.com", password="ClaveSegura2026"
    )
    usuario.groups.add(Group.objects.get_or_create(name="operador")[0])
    Empleado.objects.create(
        usuario=usuario, sede=sede, tipo_documento="CC", num_documento="1001",
        nombres="Op", apellidos="Era", celular="3001234567", direccion="Calle 4",
    )
    http = APIClient()
    http.force_authenticate(user=usuario)

    categoria = CategoriaMenu.objects.create(nombre="Platos")
    producto = Producto.objects.create(
        categoria=categoria, nombre="Hamburguesa", precio_base=Decimal("20000"),
        tiempo_preparacion=15, tipo_control_stock=Producto.TipoControlStock.PRODUCTO,
    )
    inventario = InventarioProducto.objects.create(sede=sede, producto=producto, stock_actual=5)
    grande = ProductoTamano.objects.create(
        producto=producto, nombre="Grande", precio_adicional=Decimal("5000")
    )
    queso = Insumo.objects.create(nombre="Queso", unidad_medida=Insumo.UnidadMedida.choices[0][0])
    InventarioInsumo.objects.create(sede=sede, insumo=queso, stock_actual=Decimal("10"))
    extra = Adicion.objects.create(insumo=queso, nombre="Queso extra", precio=Decimal("2000"))
    ProductoAdicion.objects.create(producto=producto, adicion=extra, max_cantidad=2)
    return SimpleNamespace(
        http=http, usuario=usuario, producto=producto, inventario=inventario,
        grande=grande, extra=extra,
    )


def _body(m, cantidad=2, **item):
    return {
        "origen": "mostrador", "metodo_pago": "efectivo",
        "items": [{"producto_id": m.producto.pk, "cantidad": cantidad, **item}],
    }


def test_pedido_con_tamano_y_adicion_suma_bien_y_cuadra_con_la_factura(m):
    resp = m.http.post(
        URL,
        _body(m, tamano_id=m.grande.pk, adiciones=[{"adicion_id": m.extra.pk, "cantidad": 1}]),
        format="json",
    )

    assert resp.status_code == 201, resp.data
    detalle = DetallePedido.objects.get(pedido_id=resp.data["id"])
    # (20000 + 5000 size) per unit; the add-on goes into the line subtotal.
    assert detalle.precio_unitario == Decimal("25000")
    assert detalle.subtotal == (Decimal("25000") + Decimal("2000")) * 2
    assert Decimal(resp.data["factura"]["subtotal"]) == detalle.subtotal
    assert Decimal(resp.data["factura"]["total"]) == detalle.subtotal  # counter: no delivery


def test_crear_el_pedido_descuenta_stock(m):
    resp = m.http.post(URL, _body(m, cantidad=2, tamano_id=m.grande.pk), format="json")

    assert resp.status_code == 201, resp.data
    m.inventario.refresh_from_db()
    assert m.inventario.stock_actual == 3


def test_sin_stock_suficiente_se_rechaza_sin_crear_el_pedido(m):
    resp = m.http.post(URL, _body(m, cantidad=6, tamano_id=m.grande.pk), format="json")

    assert resp.status_code == 400
    assert resp.data["items"][0]["motivo"] == "Solo quedan 5 unidades."
    assert not Pedido.objects.exists()
    m.inventario.refresh_from_db()
    assert m.inventario.stock_actual == 5


def test_producto_con_tamanos_exige_elegir_uno(m):
    resp = m.http.post(URL, _body(m), format="json")

    assert resp.status_code == 400
    assert resp.data["items"][0]["motivo"] == "Debes elegir un tamaño."


def test_queda_el_primer_registro_del_historial(m):
    resp = m.http.post(URL, _body(m, tamano_id=m.grande.pk), format="json")

    historial = HistorialEstadoPedido.objects.get(pedido_id=resp.data["id"])
    assert historial.estado == EstadoPedido.RECIBIDO
    assert historial.usuario == m.usuario


def test_producto_sin_control_marcado_agotado_por_cocina_se_rechaza(m):
    """'Sin control' no descuenta stock, pero si cocina lo reportó agotado no se puede pedir."""
    limonada = Producto.objects.create(
        categoria=m.producto.categoria, nombre="Limonada", precio_base=Decimal("6000"),
        tiempo_preparacion=2,  # tipo_control_stock por defecto: NINGUNO
    )
    InventarioProducto.objects.create(
        sede=m.inventario.sede, producto=limonada, stock_actual=50, disponible=False
    )
    body = _body(m, cantidad=1, tamano_id=m.grande.pk)
    body["items"].append({"producto_id": limonada.pk, "cantidad": 1})

    resp = m.http.post(URL, body, format="json")

    assert resp.status_code == 400
    assert resp.data["items"] == [{"indice": 1, "nombre": "Limonada", "motivo": "Producto agotado."}]
    assert not Pedido.objects.exists()


def test_producto_sin_control_disponible_se_pide_sin_tocar_stock(m):
    limonada = Producto.objects.create(
        categoria=m.producto.categoria, nombre="Limonada", precio_base=Decimal("6000"),
        tiempo_preparacion=2,
    )
    inventario = InventarioProducto.objects.create(
        sede=m.inventario.sede, producto=limonada, stock_actual=50
    )

    resp = m.http.post(URL, {**_body(m), "items": [{"producto_id": limonada.pk, "cantidad": 3}]}, format="json")

    assert resp.status_code == 201, resp.data
    inventario.refresh_from_db()
    assert inventario.stock_actual == 50
