"""
Pasos de tests/features/cancelar_pedido.feature (HU-25).

El .feature usa los nombres de los estados como los ve el cliente ("En preparación");
aquí se traducen al valor que guarda el modelo con las etiquetas de EstadoPedido.
"""
from datetime import date
from decimal import Decimal
from types import SimpleNamespace

import pytest
from pytest_bdd import given, parsers, scenarios, then, when
from rest_framework.test import APIClient

from inventario.models import InventarioProducto
from menu.models import CategoriaMenu, Producto
from pedidos.models import EstadoPedido, Pedido
from sedes.models import Ciudad, Sede, ZonaCobertura
from usuarios.models import Cliente, DireccionEntrega, Usuario

pytestmark = pytest.mark.django_db

scenarios("features/cancelar_pedido.feature")

CONFIRMAR = "/api/pedidos/confirmar/"
ESTADO_POR_NOMBRE = {etiqueta: valor for valor, etiqueta in EstadoPedido.choices}


def cancelar_url(pedido):
    return f"/api/pedidos/{pedido.pk}/cancelar/"


def cliente_con_direccion(ciudad, email, celular):
    usuario = Usuario.objects.create_user(username=email, email=email, password="Clave2026x")
    cliente = Cliente.objects.create(
        usuario=usuario, tipo_documento="CC", num_documento=celular, nombres="Ana",
        apellidos="Prueba", celular=celular, fecha_nacimiento=date(2000, 1, 1),
    )
    direccion = DireccionEntrega.objects.create(
        ciudad=ciudad, cliente=cliente, direccion="Calle 5 # 6-7", latitud=3.46, longitud=-76.53,
    )
    api = APIClient()
    api.force_authenticate(user=usuario)
    return api, direccion


@given("que pedí 2 hamburguesas y quedan 3 en el inventario de la sede", target_fixture="ctx")
def pedido_de_dos_hamburguesas():
    ciudad = Ciudad.objects.create(nombre="Cali")
    sede = Sede.objects.create(
        ciudad=ciudad, nombre="Norte", direccion="Calle 1 # 2-3", latitud=3.45,
        longitud=-76.53, barrio="Granada", telefono="3000000000", correo="s@correo.com",
    )
    ZonaCobertura.objects.create(
        sede=sede, nombre="Zona 1", radio=5, centro_latitud=3.45, centro_longitud=-76.53,
        tarifa_domicilio=Decimal("3000"), tiempo_estimado=40, pedido_minimo=Decimal("0"),
    )
    producto = Producto.objects.create(
        categoria=CategoriaMenu.objects.create(nombre="Platos"), nombre="Hamburguesa",
        precio_base=Decimal("20000"), tiempo_preparacion=15,
        tipo_control_stock=Producto.TipoControlStock.PRODUCTO,
    )
    inventario = InventarioProducto.objects.create(sede=sede, producto=producto, stock_actual=5)
    api, direccion = cliente_con_direccion(ciudad, "cli@correo.com", "3001234567")

    respuesta = api.post(
        CONFIRMAR,
        {"sede_id": sede.pk, "direccion_id": direccion.pk, "metodo_pago": "tarjeta",
         "items": [{"producto_id": producto.pk, "cantidad": 2}]},
        format="json",
    )
    assert respuesta.status_code == 201, respuesta.data
    inventario.refresh_from_db()
    assert inventario.stock_actual == 3
    return SimpleNamespace(
        ciudad=ciudad, api=api, pedido=Pedido.objects.get(), inventario=inventario, respuesta=None,
    )


@given(parsers.parse('que mi pedido está "{estado}"'))
def pedido_en_estado(ctx, estado):
    Pedido.objects.filter(pk=ctx.pedido.pk).update(estado=ESTADO_POR_NOMBRE[estado])


@given("que ya cancelé mi pedido")
def ya_cancelado(ctx):
    assert ctx.api.post(cancelar_url(ctx.pedido)).status_code == 200


@given("que otro cliente intenta cancelar mi pedido")
def otro_cliente_cancela(ctx):
    otro, _ = cliente_con_direccion(ctx.ciudad, "otro@correo.com", "3009999999")
    ctx.respuesta = otro.post(cancelar_url(ctx.pedido))


@when("cancelo el pedido")
def cancelo(ctx):
    ctx.respuesta = ctx.api.post(cancelar_url(ctx.pedido))


@then(parsers.parse('el pedido queda "{estado}"'))
def pedido_queda(ctx, estado):
    assert ctx.respuesta.status_code == 200, ctx.respuesta.data
    ctx.pedido.refresh_from_db()
    assert ctx.pedido.estado == ESTADO_POR_NOMBRE[estado]


@then(parsers.parse('el pedido sigue "{estado}"'))
def pedido_sigue(ctx, estado):
    ctx.pedido.refresh_from_db()
    assert ctx.pedido.estado == ESTADO_POR_NOMBRE[estado]


@then("veo que el pedido no se puede cancelar")
def no_se_puede(ctx):
    assert ctx.respuesta.status_code == 400
    # Ya en cocina: cancelacion_no_permitida · ya cerrado (cancelado o entregado): pedido_cerrado
    assert ctx.respuesta.data["codigo"] in {"cancelacion_no_permitida", "pedido_cerrado"}


@then("no encuentra el pedido")
def no_lo_encuentra(ctx):
    assert ctx.respuesta.status_code == 404


@then(parsers.parse("el inventario de la sede vuelve a {cantidad:d} hamburguesas"))
@then(parsers.parse("el inventario de la sede sigue en {cantidad:d} hamburguesas"))
def inventario_en(ctx, cantidad):
    ctx.inventario.refresh_from_db()
    assert ctx.inventario.stock_actual == cantidad
