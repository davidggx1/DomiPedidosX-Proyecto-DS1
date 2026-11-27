"""
Pasos de tests/features/pedido_minimo.feature (HU-57).

Los criterios de aceptación están escritos en Gherkin (Dado / Cuando / Entonces) y
pytest-bdd los ejecuta contra la API real. Cada línea del .feature corresponde a una
función de este archivo con el mismo texto.
"""
from datetime import date
from decimal import Decimal
from types import SimpleNamespace

import pytest
from pytest_bdd import given, parsers, scenarios, then, when
from rest_framework.test import APIClient

from menu.models import CategoriaMenu, Producto
from pedidos.models import Pedido
from sedes.models import Ciudad, Sede, ZonaCobertura
from usuarios.models import Cliente, DireccionEntrega, Usuario

pytestmark = pytest.mark.django_db

scenarios("features/pedido_minimo.feature")

CONFIRMAR = "/api/pedidos/confirmar/"


def pesos(texto):
    """'$10.000' -> Decimal('10000'). En Colombia el punto separa los miles."""
    return Decimal(texto.replace("$", "").replace(".", "").strip())


@given(
    parsers.parse("que mi dirección está en una zona con pedido mínimo de {minimo} y domicilio de {domicilio}"),
    target_fixture="ctx",
)
def zona_con_minimo(minimo, domicilio):
    ciudad = Ciudad.objects.create(nombre="Cali")
    sede = Sede.objects.create(
        ciudad=ciudad, nombre="Norte", direccion="Calle 1 # 2-3", latitud=3.45,
        longitud=-76.53, barrio="Granada", telefono="3000000000", correo="s@correo.com",
    )
    zona = ZonaCobertura.objects.create(
        sede=sede, nombre="Zona 1", radio=5, centro_latitud=3.45, centro_longitud=-76.53,
        tarifa_domicilio=pesos(domicilio), tiempo_estimado=40, pedido_minimo=pesos(minimo),
    )
    usuario = Usuario.objects.create_user(username="cli@correo.com", email="cli@correo.com", password="Clave2026x")
    cliente = Cliente.objects.create(
        usuario=usuario, tipo_documento="CC", num_documento="123", nombres="Ana",
        apellidos="Prueba", celular="3001234567", fecha_nacimiento=date(2000, 1, 1),
    )
    direccion = DireccionEntrega.objects.create(
        ciudad=ciudad, cliente=cliente, direccion="Calle 5 # 6-7", latitud=3.46, longitud=-76.53,
    )
    producto = Producto.objects.create(
        categoria=CategoriaMenu.objects.create(nombre="Platos"), nombre="Plato del día",
        precio_base=Decimal("1000"), tiempo_preparacion=15,
    )
    api = APIClient()
    api.force_authenticate(user=usuario)
    return SimpleNamespace(sede=sede, zona=zona, direccion=direccion, producto=producto, api=api, respuesta=None)


@given("que la zona no tiene pedido mínimo")
def zona_sin_minimo(ctx):
    ctx.zona.pedido_minimo = Decimal("0")
    ctx.zona.save()


@given(parsers.parse("que mi carrito suma {subtotal}"))
def carrito_que_suma(ctx, subtotal):
    # Un solo producto cuyo precio es el subtotal buscado, así cualquier valor límite es exacto
    ctx.producto.precio_base = pesos(subtotal)
    ctx.producto.save()


@when("confirmo el pedido")
def confirmo(ctx):
    ctx.respuesta = ctx.api.post(
        CONFIRMAR,
        {
            "sede_id": ctx.sede.pk,
            "direccion_id": ctx.direccion.pk,
            "metodo_pago": "tarjeta",
            "items": [{"producto_id": ctx.producto.pk, "cantidad": 1}],
        },
        format="json",
    )


@then("el pedido queda registrado")
def pedido_registrado(ctx):
    assert ctx.respuesta.status_code == 201, ctx.respuesta.data
    assert Pedido.objects.count() == 1


@then("el pedido no se envía")
def pedido_rechazado(ctx):
    assert ctx.respuesta.status_code == 400


@then(parsers.parse("veo que me faltan {faltante} para el mínimo"))
def veo_faltante(ctx, faltante):
    assert Decimal(ctx.respuesta.data["faltante"]) == pesos(faltante)
    assert "mínimo" in ctx.respuesta.data["detail"]


@then("no se crea ningún pedido")
def sin_pedidos(ctx):
    assert not Pedido.objects.exists()
