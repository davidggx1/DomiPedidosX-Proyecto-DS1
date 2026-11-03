"""HU-13 · Disponibilidad de productos por sede: aislamiento, reactivación y carrito."""
from decimal import Decimal

import pytest
from django.contrib.auth.models import Group
from rest_framework.test import APIClient

from inventario.models import InventarioProducto
from menu.models import CategoriaMenu, Producto
from sedes.models import Ciudad, Sede
from usuarios.models import Empleado, Usuario


def crear_sede(nombre, activa=True):
    ciudad, _ = Ciudad.objects.get_or_create(nombre="Cali")
    return Sede.objects.create(
        ciudad=ciudad, nombre=nombre, direccion="Cra 1 # 2-3", activa=activa,
        latitud=3.45, longitud=-76.53, barrio="Centro",
        telefono="3000000000", correo=f"{nombre.lower().replace(' ', '')}@domi.com",
    )


def crear_usuario(correo, grupo, sede=None, documento="100"):
    usuario = Usuario.objects.create_user(username=correo, email=correo, password="ClaveSegura2026")
    usuario.groups.add(Group.objects.get_or_create(name=grupo)[0])
    if sede is not None:
        Empleado.objects.create(
            usuario=usuario, sede=sede, tipo_documento="CC", num_documento=documento,
            nombres="Ana", apellidos="Pérez", celular="3000000000", direccion="Calle 1",
        )
    return usuario


def api_de(usuario=None):
    api = APIClient()
    if usuario:
        api.force_authenticate(user=usuario)
    return api


def url(producto):
    return f"/api/menu/productos/{producto.id}/disponibilidad/"


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
def operador_centro(centro):
    return api_de(crear_usuario("op.centro@correo.com", "operador", centro, "101"))


@pytest.fixture
def administrador(db):
    return api_de(crear_usuario("admin@correo.com", "administrador"))


# --- Aislamiento entre sedes -------------------------------------------------


def test_desactivar_en_una_sede_no_afecta_a_la_otra(operador_centro, producto, centro, sur):
    respuesta = operador_centro.patch(url(producto), {"sede": centro.id, "disponible": False}, format="json")

    assert respuesta.status_code == 200
    assert InventarioProducto.objects.get(sede=centro, producto=producto).disponible is False
    assert InventarioProducto.objects.get(sede=sur, producto=producto).disponible is True
    assert disponible_en_menu(centro, producto) is False
    assert disponible_en_menu(sur, producto) is True


def test_operador_no_puede_cambiar_otra_sede(operador_centro, producto, sur):
    respuesta = operador_centro.patch(url(producto), {"sede": sur.id, "disponible": False}, format="json")

    assert respuesta.status_code == 403
    assert InventarioProducto.objects.get(sede=sur, producto=producto).disponible is True


def test_operador_sin_sede_asignada_no_puede_cambiar(producto, centro):
    api = api_de(crear_usuario("op.libre@correo.com", "operador"))
    respuesta = api.patch(url(producto), {"sede": centro.id, "disponible": False}, format="json")
    assert respuesta.status_code == 403


def test_administrador_puede_cambiar_cualquier_sede(administrador, producto, sur):
    respuesta = administrador.patch(url(producto), {"sede": sur.id, "disponible": False}, format="json")
    assert respuesta.status_code == 200
    assert InventarioProducto.objects.get(sede=sur, producto=producto).disponible is False


def test_estado_indica_que_sedes_puede_editar_el_operador(operador_centro, producto, centro, sur):
    respuesta = operador_centro.get(url(producto))

    assert respuesta.status_code == 200
    estado = {fila["sede"]: fila for fila in respuesta.data}
    assert estado[centro.id]["editable"] is True
    assert estado[sur.id]["editable"] is False
    assert estado[centro.id]["disponible"] is True


# --- Reactivación ------------------------------------------------------------


def test_reactivar_vuelve_a_mostrarlo_disponible(operador_centro, producto, centro):
    operador_centro.patch(url(producto), {"sede": centro.id, "disponible": False}, format="json")
    assert disponible_en_menu(centro, producto) is False

    respuesta = operador_centro.patch(url(producto), {"sede": centro.id, "disponible": True}, format="json")

    assert respuesta.status_code == 200
    assert disponible_en_menu(centro, producto) is True


def test_activar_en_sede_sin_registro_lo_crea(administrador, centro):
    categoria = CategoriaMenu.objects.create(nombre="Bebidas")
    nuevo = Producto.objects.create(
        categoria=categoria, nombre="Limonada", precio_base=Decimal("6000"), tiempo_preparacion=5
    )
    respuesta = administrador.patch(url(nuevo), {"sede": centro.id, "disponible": True}, format="json")

    assert respuesta.status_code == 200
    assert InventarioProducto.objects.get(sede=centro, producto=nuevo).disponible is True


# --- Validaciones y permisos -------------------------------------------------


@pytest.mark.parametrize(
    "datos",
    [{}, {"sede": 9999, "disponible": False}, {"disponible": False}, {"sede": 1}],
)
def test_datos_invalidos_devuelven_400(administrador, producto, datos):
    assert administrador.patch(url(producto), datos, format="json").status_code == 400


def test_sede_inactiva_no_se_puede_cambiar(administrador, producto):
    inactiva = crear_sede("Norte", activa=False)
    respuesta = administrador.patch(url(producto), {"sede": inactiva.id, "disponible": True}, format="json")
    assert respuesta.status_code == 400


def test_cliente_y_anonimo_no_pueden_cambiar(producto, centro):
    cliente = api_de(crear_usuario("cliente@correo.com", "cliente"))
    datos = {"sede": centro.id, "disponible": False}
    assert cliente.patch(url(producto), datos, format="json").status_code == 403
    assert APIClient().patch(url(producto), datos, format="json").status_code in (401, 403)


# --- Hook del carrito (el cierre llega con HU-23) ----------------------------


def test_carrito_valido_si_todo_sigue_disponible(producto, centro):
    respuesta = APIClient().post(
        f"/api/menu/sedes/{centro.id}/validar-carrito/", {"productos": [producto.id]}, format="json"
    )
    assert respuesta.status_code == 200
    assert respuesta.data == {"valido": True, "no_disponibles": []}


def test_carrito_avisa_si_se_desactivo_antes_de_confirmar(operador_centro, producto, centro, sur):
    operador_centro.patch(url(producto), {"sede": centro.id, "disponible": False}, format="json")

    en_centro = APIClient().post(
        f"/api/menu/sedes/{centro.id}/validar-carrito/", {"productos": [producto.id]}, format="json"
    )
    en_sur = APIClient().post(
        f"/api/menu/sedes/{sur.id}/validar-carrito/", {"productos": [producto.id]}, format="json"
    )

    assert en_centro.data["valido"] is False
    assert en_centro.data["no_disponibles"] == [{"id": producto.id, "nombre": "Clásica"}]
    assert en_sur.data["valido"] is True


def test_carrito_con_datos_invalidos_devuelve_400(centro):
    respuesta = APIClient().post(
        f"/api/menu/sedes/{centro.id}/validar-carrito/", {"productos": "1"}, format="json"
    )
    assert respuesta.status_code == 400
