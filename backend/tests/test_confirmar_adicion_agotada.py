"""Al confirmar, una adición agotada se nombra en el error (no "Una adición está agotada")."""
from datetime import date
from decimal import Decimal

import pytest
from rest_framework.test import APIClient

from inventario.models import InventarioInsumo, InventarioProducto
from menu.models import Adicion, CategoriaMenu, Insumo, Producto, ProductoAdicion
from pedidos.models import Pedido
from sedes.models import Ciudad, Sede, ZonaCobertura
from usuarios.models import Cliente, DireccionEntrega, Usuario

pytestmark = pytest.mark.django_db


@pytest.fixture
def m():
    ciudad = Ciudad.objects.create(nombre="Cali")
    sede = Sede.objects.create(
        ciudad=ciudad, nombre="Sur", direccion="Calle 1 # 2-3", latitud=3.45, longitud=-76.53,
        barrio="Ciudad Jardín", telefono="3000000000", correo="sur@correo.com",
    )
    ZonaCobertura.objects.create(
        sede=sede, nombre="Zona Sur", radio=5, centro_latitud=3.45, centro_longitud=-76.53,
        tarifa_domicilio=Decimal("3000"), tiempo_estimado=40, pedido_minimo=Decimal("0"),
    )
    usuario = Usuario.objects.create_user(username="cli@correo.com", email="cli@correo.com", password="Clave2026x")
    cliente = Cliente.objects.create(
        usuario=usuario, tipo_documento="CC", num_documento="3001234567", nombres="Ana",
        apellidos="Prueba", celular="3001234567", fecha_nacimiento=date(2000, 1, 1),
    )
    direccion = DireccionEntrega.objects.create(
        ciudad=ciudad, cliente=cliente, direccion="Calle 5 # 6-7", latitud=3.46, longitud=-76.53,
    )
    pizza = Producto.objects.create(
        categoria=CategoriaMenu.objects.create(nombre="Pizzas"), nombre="Pizza pepperoni",
        precio_base=Decimal("30000"), tiempo_preparacion=20,
    )
    InventarioProducto.objects.create(sede=sede, producto=pizza, disponible=True)

    def adicion(nombre, insumo, stock):
        insumo = Insumo.objects.create(nombre=insumo, unidad_medida=Insumo.UnidadMedida.GRAMO)
        InventarioInsumo.objects.create(sede=sede, insumo=insumo, stock_actual=stock)
        extra = Adicion.objects.create(insumo=insumo, nombre=nombre, precio=Decimal("3000"))
        ProductoAdicion.objects.create(producto=pizza, adicion=extra, max_cantidad=2)
        return extra

    api = APIClient()
    api.force_authenticate(user=usuario)
    return {
        "api": api, "sede": sede, "direccion": direccion, "pizza": pizza,
        "queso": adicion("Queso extra", "Queso", 0),
        "champinones": adicion("Champiñones", "Champiñón", 0),
        "oregano": adicion("Orégano", "Orégano seco", 100),
    }


def confirmar(m, *adiciones):
    return m["api"].post(
        "/api/pedidos/confirmar/",
        {
            "sede_id": m["sede"].pk, "direccion_id": m["direccion"].pk, "metodo_pago": "efectivo",
            "items": [{
                "producto_id": m["pizza"].pk, "cantidad": 1,
                "adiciones": [{"adicion_id": a.pk, "cantidad": 1} for a in adiciones],
            }],
        },
        format="json",
    )


def test_el_error_dice_cual_adicion_esta_agotada(m):
    r = confirmar(m, m["queso"], m["oregano"])

    assert r.status_code == 400
    assert [(e["nombre"], e["motivo"]) for e in r.data["items"]] == [
        ("Pizza pepperoni", "Adición agotada: Queso extra."),
    ]
    assert not Pedido.objects.exists()


def test_con_dos_adiciones_agotadas_nombra_cada_una(m):
    r = confirmar(m, m["queso"], m["champinones"])

    motivos = sorted(e["motivo"] for e in r.data["items"])
    assert motivos == ["Adición agotada: Champiñones.", "Adición agotada: Queso extra."]


def test_sin_adiciones_agotadas_el_pedido_se_crea(m):
    assert confirmar(m, m["oregano"]).status_code == 201
