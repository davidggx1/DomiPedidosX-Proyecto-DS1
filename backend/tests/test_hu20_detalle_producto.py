import pytest
from decimal import Decimal
from django.urls import reverse
from rest_framework import status
from menu.models import (
    Adicion,
    CategoriaMenu,
    Insumo,
    Producto,
    ProductoAdicion,
    ProductoInsumo,
)

@pytest.fixture
def datos_producto_detalle(db):
    categoria = CategoriaMenu.objects.create(nombre="Hamburguesas")
    producto = Producto.objects.create(
        nombre="Hamburguesa Doble Carne",
        descripcion="Doble carne de res con queso cheddar",
        precio_base=Decimal("25000.00"),
        tiempo_preparacion=15,
        categoria=categoria,
        activo=True,
    )

    insumo = Insumo.objects.create(nombre="Cebolla Caramelizada", unidad_medida="g")
    ProductoInsumo.objects.create(
        producto=producto,
        insumo=insumo,
        cantidad_necesaria=Decimal("30.00"),
        es_excluible=True,
    )

    # Insumo para la adición
    insumo_adicion = Insumo.objects.create(nombre="Tocineta Extra Insumo", unidad_medida="g")
    adicion = Adicion.objects.create(
        nombre="Tocineta Extra",
        precio=Decimal("4000.00"),
        insumo=insumo_adicion,  # <--- Asignamos el insumo obligatorio
    )

    ProductoAdicion.objects.create(
        producto=producto,
        adicion=adicion,
        max_cantidad=2,
    )

    return producto


@pytest.mark.django_db
def test_cliente_anonimo_puede_ver_detalle_producto(client, datos_producto_detalle):
    """HU-20: Un cliente no autenticado puede consultar el detalle completo de un producto."""
    url = f"/api/menu/productos/{datos_producto_detalle.id}/"
    respuesta = client.get(url)

    assert respuesta.status_code == status.HTTP_200_OK
    data = respuesta.data

    assert data["id"] == datos_producto_detalle.id
    assert data["nombre"] == "Hamburguesa Doble Carne"
    assert data["precio_base"] == "25000.00"
    assert data["categoria_nombre"] == "Hamburguesas"
    assert data["disponible"] is True

    assert len(data["ingredientes"]) == 1
    assert data["ingredientes"][0]["nombre"] == "Cebolla Caramelizada"
    assert data["ingredientes"][0]["es_excluible"] is True

    assert len(data["adiciones"]) == 1
    assert data["adiciones"][0]["nombre"] == "Tocineta Extra"
    assert data["adiciones"][0]["precio"] == "4000.00"


@pytest.mark.django_db
def test_detalle_producto_inexistente_devuelve_404(client):
    """HU-20: Consultar un ID de producto que no existe retorna HTTP 404."""
    url = "/api/menu/productos/99999/"
    respuesta = client.get(url)

    assert respuesta.status_code == status.HTTP_404_NOT_FOUND