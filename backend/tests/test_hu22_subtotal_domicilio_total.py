import json
import pytest
from decimal import Decimal
from rest_framework import status
from menu.models import CategoriaMenu, Producto, Adicion, Insumo, ProductoAdicion
from sedes.models import Sede, Ciudad
from inventario.models import InventarioProducto


@pytest.fixture
def datos_carrito(db):
    ciudad = Ciudad.objects.create(nombre="Cali")

    sede = Sede.objects.create(
        nombre="Sede Centro",
        direccion="Calle 10",
        ciudad=ciudad,
        latitud=Decimal("3.4516"),
        longitud=Decimal("-76.5320"),
        activa=True,
    )
    categoria = CategoriaMenu.objects.create(nombre="Pizzas", activa=True)

    producto = Producto.objects.create(
        nombre="Pizza Hawaiana",
        precio_base=Decimal("30000.00"),
        tiempo_preparacion=20,
        categoria=categoria,
        activo=True,
    )
    InventarioProducto.objects.create(sede=sede, producto=producto, disponible=True, stock_actual=10)

    insumo = Insumo.objects.create(nombre="Queso Extra Insumo", unidad_medida="g")
    adicion = Adicion.objects.create(nombre="Queso Extra", precio=Decimal("5000.00"), insumo=insumo, activa=True)
    ProductoAdicion.objects.create(producto=producto, adicion=adicion, max_cantidad=2)

    return {"sede": sede, "producto": producto, "adicion": adicion}


@pytest.mark.django_db
def test_calculo_subtotal_domicilio_y_total_exitoso(client, datos_carrito):
    """HU-22: Verifica que el subtotal, domicilio provisional y total se calculen adecuadamente."""
    sede = datos_carrito["sede"]
    producto = datos_carrito["producto"]
    adicion = datos_carrito["adicion"]

    payload = {
        "lineas": [
            {
                "producto": producto.id,
                "tamano": None,
                "adiciones": [{"adicion": adicion.id, "cantidad": 1}],
                "exclusiones": [],
                "cantidad": 2,
            }
        ]
    }

    url = f"/api/menu/sedes/{sede.id}/carrito/resumen/"
    res = client.post(
        url,
        data=json.dumps(payload),
        content_type="application/json"
    )

    assert res.status_code == status.HTTP_200_OK, res.data
    data = res.data

    assert data["subtotal"] == "70000.00"
    assert data["costo_domicilio"] == "4000.00"
    assert data["total"] == "74000.00"
    assert len(data["lineas"]) == 1


@pytest.mark.django_db
def test_calculo_carrito_vacio_domicilio_cero(client, datos_carrito):
    """HU-22: Un carrito vacío debe arrojar subtotal, domicilio y total en cero."""
    sede = datos_carrito["sede"]
    payload = {"lineas": []}

    url = f"/api/menu/sedes/{sede.id}/carrito/resumen/"
    res = client.post(
        url,
        data=json.dumps(payload),
        content_type="application/json"
    )

    assert res.status_code == status.HTTP_200_OK, res.data
    assert res.data["subtotal"] == "0.00"
    assert res.data["costo_domicilio"] == "0.00"
    assert res.data["total"] == "0.00"