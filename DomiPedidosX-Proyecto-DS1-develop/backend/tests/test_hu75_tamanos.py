"""Pruebas de HU-75 · Tamaños de un producto (SCRUM-32)."""
from decimal import Decimal

import pytest
from django.contrib.auth.models import Group
from rest_framework.test import APIClient

from menu.models import CategoriaMenu, Producto, ProductoTamano
from pedidos.models import DetallePedido, Pedido
from sedes.models import Ciudad, Sede
from usuarios.models import Usuario

pytestmark = pytest.mark.django_db
CLAVE = "ClaveSegura#2026"


def usuario_operador():
    usuario = Usuario.objects.create_user(
        username="operador-hu75@correo.com", email="operador-hu75@correo.com", password=CLAVE
    )
    usuario.groups.add(Group.objects.get_or_create(name="operador")[0])
    return usuario


@pytest.fixture
def api():
    cliente = APIClient()
    cliente.force_authenticate(usuario_operador())
    return cliente


@pytest.fixture
def producto():
    categoria = CategoriaMenu.objects.create(nombre="Bebidas")
    return Producto.objects.create(
        categoria=categoria, nombre="Limonada", precio_base=5000, tiempo_preparacion=5
    )


def url(producto):
    return f"/api/menu/productos/{producto.id}/tamanos/"


def test_crear_tamano(api, producto):
    respuesta = api.post(url(producto), {"nombre": "Grande", "precio_adicional": "2000"}, format="json")
    assert respuesta.status_code == 201
    assert respuesta.data["nombre"] == "Grande"
    assert Decimal(respuesta.data["precio_adicional"]) == Decimal("2000")


@pytest.mark.parametrize("nombre", ["", "   "])
def test_nombre_obligatorio(api, producto, nombre):
    respuesta = api.post(url(producto), {"nombre": nombre, "precio_adicional": "0"}, format="json")
    assert respuesta.status_code == 400
    assert "nombre" in respuesta.data


def test_precio_negativo_no_permitido(api, producto):
    respuesta = api.post(url(producto), {"nombre": "Pequeño", "precio_adicional": "-1"}, format="json")
    assert respuesta.status_code == 400
    assert "precio_adicional" in respuesta.data


def test_precio_cero_permitido(api, producto):
    respuesta = api.post(url(producto), {"nombre": "Personal", "precio_adicional": "0"}, format="json")
    assert respuesta.status_code == 201


def test_editar_precio(api, producto):
    tamano = ProductoTamano.objects.create(producto=producto, nombre="Grande", precio_adicional=1000)
    respuesta = api.patch(f"{url(producto)}{tamano.id}/", {"precio_adicional": "2500"}, format="json")
    assert respuesta.status_code == 200
    tamano.refresh_from_db()
    assert tamano.precio_adicional == Decimal("2500")


def test_eliminar_es_logico(api, producto):
    tamano = ProductoTamano.objects.create(producto=producto, nombre="Grande", precio_adicional=1000)
    respuesta = api.delete(f"{url(producto)}{tamano.id}/")
    assert respuesta.status_code == 204
    tamano.refresh_from_db()
    assert tamano.activo is False
    assert api.get(url(producto)).data == []


def test_editar_y_eliminar_no_altera_pedido_historico(api, producto):
    tamano = ProductoTamano.objects.create(producto=producto, nombre="Grande", precio_adicional=1000)
    ciudad = Ciudad.objects.create(nombre="Cali")
    sede = Sede.objects.create(
        ciudad=ciudad, nombre="Sede Centro", direccion="Cra 1 # 2-3", latitud=3.45,
        longitud=-76.53, barrio="Centro", telefono="3000000000", correo="centro@domi.com",
    )
    pedido = Pedido.objects.create(sede=sede, numero_pedido="HU75-001")
    detalle = DetallePedido.objects.create(
        pedido=pedido, producto=producto, producto_tamano=tamano, cantidad=1,
        precio_unitario=6000, subtotal=6000,
    )
    api.patch(f"{url(producto)}{tamano.id}/", {"precio_adicional": "3000"}, format="json")
    api.delete(f"{url(producto)}{tamano.id}/")
    detalle.refresh_from_db()
    assert detalle.producto_tamano_id == tamano.id
    assert detalle.precio_unitario == Decimal("6000")


def test_sin_autenticacion_no_puede_gestionar_tamanos(producto):
    assert APIClient().get(url(producto)).status_code in (401, 403)
