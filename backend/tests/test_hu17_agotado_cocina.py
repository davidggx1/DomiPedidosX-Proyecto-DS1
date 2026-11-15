"""HU-17 · Cocina reporta un producto como agotado desde su vista."""
from decimal import Decimal
from unittest import mock

import pytest
from django.contrib.auth.models import Group
from rest_framework.test import APIClient

from inventario.models import InventarioProducto, ReporteAgotado
from menu import agotados
from menu.models import CategoriaMenu, Producto
from sedes.models import Ciudad, Sede
from usuarios.models import Empleado, Usuario


def crear_sede(nombre):
    ciudad, _ = Ciudad.objects.get_or_create(nombre="Cali")
    return Sede.objects.create(
        ciudad=ciudad, nombre=nombre, direccion="Cra 1 # 2-3", latitud=3.45, longitud=-76.53,
        barrio="Centro", telefono="3000000000", correo=f"{nombre.lower()}@domi.com",
    )


def crear_usuario(correo, grupo, sede=None, documento="100"):
    usuario = Usuario.objects.create_user(username=correo, email=correo, password="ClaveSegura2026")
    usuario.groups.add(Group.objects.get_or_create(name=grupo)[0])
    if sede is not None:
        Empleado.objects.create(
            usuario=usuario, sede=sede, tipo_documento="CC", num_documento=documento,
            nombres="Carla", apellidos="Gómez", celular="3000000000", direccion="Calle 1",
        )
    return usuario


def api_de(usuario):
    api = APIClient()
    api.force_authenticate(user=usuario)
    return api


def url_agotado(producto):
    return f"/api/menu/cocina/productos/{producto.id}/agotado/"


def disponible_en_menu(sede, producto):
    respuesta = APIClient().get(f"/api/menu/sedes/{sede.id}/menu/")
    for categoria in respuesta.data["categorias"]:
        for item in categoria["productos"]:
            if item["id"] == producto.id:
                return item["disponible"]
    raise AssertionError("El producto no aparece en el menú")


@pytest.fixture
def centro(db):
    return crear_sede("Centro")


@pytest.fixture
def sur(db):
    return crear_sede("Sur")


@pytest.fixture
def producto(centro, sur):
    categoria = CategoriaMenu.objects.create(nombre="Hamburguesas")
    producto = Producto.objects.create(
        categoria=categoria, nombre="Clásica", precio_base=Decimal("18000"), tiempo_preparacion=15
    )
    InventarioProducto.objects.create(sede=centro, producto=producto, disponible=True)
    InventarioProducto.objects.create(sede=sur, producto=producto, disponible=True)
    return producto


@pytest.fixture
def cocinero(centro):
    return crear_usuario("cocina.centro@correo.com", "cocina", centro, "201")


@pytest.fixture
def cocina(cocinero):
    return api_de(cocinero)


@pytest.fixture
def avisos():
    """Captura los eventos que se envían a los operadores (sin channel layer real)."""
    with mock.patch.object(agotados, "async_to_sync") as envio:
        yield envio


# --- Criterio 1: sale del menú de la sede -----------------------------------------


def test_marcar_agotado_lo_saca_solo_del_menu_de_su_sede(
    cocina, producto, centro, sur, avisos, django_capture_on_commit_callbacks
):
    with django_capture_on_commit_callbacks(execute=True):
        respuesta = cocina.post(url_agotado(producto))

    assert respuesta.status_code == 201
    assert InventarioProducto.objects.get(sede=centro, producto=producto).disponible is False
    assert disponible_en_menu(centro, producto) is False
    # La otra sede no se toca
    assert disponible_en_menu(sur, producto) is True


def test_no_se_puede_marcar_dos_veces(cocina, producto, avisos):
    cocina.post(url_agotado(producto))
    respuesta = cocina.post(url_agotado(producto))

    assert respuesta.status_code == 400
    assert respuesta.data["codigo"] == "ya_agotado"
    assert ReporteAgotado.objects.count() == 1


def test_listado_de_cocina_muestra_disponibilidad_de_su_sede(cocina, producto, avisos):
    antes = cocina.get("/api/menu/cocina/productos/")
    assert antes.status_code == 200
    assert antes.data == [{"id": producto.id, "nombre": "Clásica", "categoria": "Hamburguesas", "disponible": True}]

    cocina.post(url_agotado(producto))

    despues = cocina.get("/api/menu/cocina/productos/", {"q": "clás"})
    assert despues.data[0]["disponible"] is False
    assert cocina.get("/api/menu/cocina/productos/", {"q": "pizza"}).data == []


# --- Criterio 2: aviso al operador con producto, hora y usuario ------------------


def test_guarda_el_reporte_y_avisa_a_los_operadores_de_la_sede(
    cocina, cocinero, producto, centro, avisos, django_capture_on_commit_callbacks
):
    with django_capture_on_commit_callbacks(execute=True):
        respuesta = cocina.post(url_agotado(producto))

    reporte = ReporteAgotado.objects.get()
    assert (reporte.sede, reporte.producto, reporte.usuario) == (centro, producto, cocinero)
    assert respuesta.data["usuario_nombre"] == "Carla Gómez"
    assert respuesta.data["producto_nombre"] == "Clásica"
    assert respuesta.data["fecha_hora"]

    grupo, evento = avisos.return_value.call_args.args
    assert grupo == f"pedidos_sede_{centro.id}"
    assert evento["type"] == "pedido.evento"
    assert evento["data"]["tipo"] == "producto_agotado"
    assert evento["data"]["reporte"] == respuesta.data


# --- Criterio 3: no se puede agregar a nuevos carritos ----------------------------


def test_el_carrito_rechaza_el_producto_agotado(cocina, producto, centro, avisos):
    cocina.post(url_agotado(producto))

    respuesta = APIClient().post(
        f"/api/menu/sedes/{centro.id}/validar-carrito/", {"productos": [producto.id]}, format="json"
    )
    assert respuesta.data["valido"] is False
    assert respuesta.data["no_disponibles"] == [{"id": producto.id, "nombre": "Clásica"}]

    linea = APIClient().post(
        f"/api/menu/sedes/{centro.id}/carrito/linea/", {"producto": producto.id, "cantidad": 1}, format="json"
    )
    assert linea.status_code == 400
    assert "no está disponible" in str(linea.data)


# --- Permisos --------------------------------------------------------------------


@pytest.mark.parametrize("grupo", ["operador", "repartidor"])
def test_otros_roles_no_pueden_reportar(grupo, producto, centro, avisos):
    api = api_de(crear_usuario(f"{grupo}@correo.com", grupo, centro, "301"))
    assert api.post(url_agotado(producto)).status_code == 403
    assert api.get("/api/menu/cocina/productos/").status_code == 403


def test_cocina_sin_sede_no_puede_reportar(producto, avisos):
    api = api_de(crear_usuario("sin.sede@correo.com", "cocina"))
    assert api.post(url_agotado(producto)).status_code == 403


def test_sin_sesion_no_puede_reportar(producto):
    assert APIClient().post(url_agotado(producto)).status_code == 401
