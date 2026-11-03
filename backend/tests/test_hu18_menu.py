"""Pruebas de HU-18 · Consultar el menú por categorías (SCRUM-36)."""
import pytest
from rest_framework.test import APIClient

from inventario.models import InventarioProducto
from menu.models import CategoriaMenu, Producto
from sedes.models import Ciudad, Sede

pytestmark = pytest.mark.django_db


def url_menu(sede):
    return f"/api/menu/sedes/{sede.id}/menu/"


def crear_sede(ciudad, nombre, activa=True):
    return Sede.objects.create(
        ciudad=ciudad, nombre=nombre, direccion="Cra 1 # 2-3", latitud=3.45, longitud=-76.53,
        barrio="Centro", telefono="3000000000", correo=f"{nombre.lower().replace(' ', '')}@domi.com",
        activa=activa,
    )


def crear_producto(categoria, nombre, **extra):
    return Producto.objects.create(
        categoria=categoria, nombre=nombre, precio_base=15000, tiempo_preparacion=10, **extra
    )


@pytest.fixture
def api():
    return APIClient()


@pytest.fixture
def ciudad():
    return Ciudad.objects.create(nombre="Cali")


@pytest.fixture
def centro(ciudad):
    return crear_sede(ciudad, "Sede Centro")


@pytest.fixture
def sur(ciudad):
    return crear_sede(ciudad, "Sede Sur")


@pytest.fixture
def hamburguesas():
    return CategoriaMenu.objects.create(nombre="Hamburguesas")


@pytest.fixture
def postres():
    return CategoriaMenu.objects.create(nombre="Postres")


@pytest.fixture
def clasica(hamburguesas, centro, sur):
    producto = crear_producto(hamburguesas, "Clásica", imagen_url="https://ejemplo.com/clasica.png")
    InventarioProducto.objects.create(sede=centro, producto=producto, disponible=True)
    InventarioProducto.objects.create(sede=sur, producto=producto, disponible=True)
    return producto


def categoria_en(respuesta, categoria):
    return next(c for c in respuesta.data["categorias"] if c["id"] == categoria.id)


def producto_en(respuesta, categoria, producto):
    return next(p for p in categoria_en(respuesta, categoria)["productos"] if p["id"] == producto.id)


# --- Criterio 1: productos agrupados por categoría con nombre, imagen y precio ---


def test_menu_agrupa_productos_por_categoria(api, centro, hamburguesas, clasica):
    respuesta = api.get(url_menu(centro))

    assert respuesta.status_code == 200
    assert respuesta.data["sede"]["nombre"] == "Sede Centro"
    producto = producto_en(respuesta, hamburguesas, clasica)
    assert producto["nombre"] == "Clásica"
    assert producto["precio"] == "15000.00"
    assert producto["imagen"] == "https://ejemplo.com/clasica.png"
    assert producto["disponible"] is True


def test_menu_es_publico(api, centro):
    assert api.get(url_menu(centro)).status_code == 200


def test_categorias_y_productos_inactivos_no_aparecen(api, centro, hamburguesas, clasica):
    inactiva = CategoriaMenu.objects.create(nombre="Temporada", activa=False)
    crear_producto(inactiva, "Especial navideño")
    retirado = crear_producto(hamburguesas, "Retirada", activo=False)

    respuesta = api.get(url_menu(centro))

    assert inactiva.id not in [c["id"] for c in respuesta.data["categorias"]]
    productos = [p["id"] for p in categoria_en(respuesta, hamburguesas)["productos"]]
    assert retirado.id not in productos
    assert clasica.id in productos


def test_lista_de_sedes_solo_muestra_activas(api, ciudad, centro):
    crear_sede(ciudad, "Sede Cerrada", activa=False)

    respuesta = api.get("/api/menu/sedes/")

    assert respuesta.status_code == 200
    assert [s["nombre"] for s in respuesta.data] == ["Sede Centro"]


def test_token_vencido_no_bloquea_el_menu(api, centro):
    api.credentials(HTTP_AUTHORIZATION="Bearer token-vencido")

    assert api.get("/api/menu/sedes/").status_code == 200
    assert api.get(url_menu(centro)).status_code == 200


def test_sede_inactiva_o_inexistente_responde_404(api, ciudad):
    cerrada = crear_sede(ciudad, "Sede Cerrada", activa=False)

    assert api.get(url_menu(cerrada)).status_code == 404
    assert api.get("/api/menu/sedes/9999/menu/").status_code == 404


# --- Criterio 2: filtrar por categoría ------------------------------------------


def test_filtrar_por_categoria(api, centro, hamburguesas, postres, clasica):
    respuesta = api.get(url_menu(centro), {"categoria": hamburguesas.id})

    assert respuesta.status_code == 200
    assert [c["id"] for c in respuesta.data["categorias"]] == [hamburguesas.id]


def test_categoria_no_numerica_responde_400(api, centro):
    respuesta = api.get(url_menu(centro), {"categoria": "abc"})

    assert respuesta.status_code == 400
    assert "categoria" in respuesta.data


# --- Criterio 3: productos desactivados o sin stock -> "No disponible" ------------


def test_producto_desactivado_en_una_sede_no_afecta_la_otra(api, centro, sur, hamburguesas, clasica):
    InventarioProducto.objects.filter(sede=sur, producto=clasica).update(disponible=False)

    en_sur = api.get(url_menu(sur))
    en_centro = api.get(url_menu(centro))

    assert producto_en(en_sur, hamburguesas, clasica)["disponible"] is False
    assert producto_en(en_centro, hamburguesas, clasica)["disponible"] is True


def test_producto_sin_stock_no_esta_disponible(api, centro, hamburguesas):
    gaseosa = crear_producto(hamburguesas, "Gaseosa", tipo_control_stock="PRODUCTO")
    InventarioProducto.objects.create(sede=centro, producto=gaseosa, stock_actual=0)

    respuesta = api.get(url_menu(centro))
    assert producto_en(respuesta, hamburguesas, gaseosa)["disponible"] is False

    InventarioProducto.objects.filter(producto=gaseosa).update(stock_actual=5)
    respuesta = api.get(url_menu(centro))
    assert producto_en(respuesta, hamburguesas, gaseosa)["disponible"] is True


def test_producto_sin_inventario_en_la_sede_no_esta_disponible(api, centro, hamburguesas):
    nuevo = crear_producto(hamburguesas, "Nueva")

    respuesta = api.get(url_menu(centro))
    assert producto_en(respuesta, hamburguesas, nuevo)["disponible"] is False


# --- Criterio 4: categoría vacía -------------------------------------------------


def test_categoria_vacia_aparece_sin_productos(api, centro, postres, clasica):
    respuesta = api.get(url_menu(centro))

    assert categoria_en(respuesta, postres)["productos"] == []


def test_filtrar_categoria_vacia(api, centro, postres, clasica):
    respuesta = api.get(url_menu(centro), {"categoria": postres.id})

    assert respuesta.status_code == 200
    assert len(respuesta.data["categorias"]) == 1
    assert respuesta.data["categorias"][0]["productos"] == []
