import pytest
from django.contrib.auth.models import Group
from rest_framework.test import APIClient

from menu.models import CategoriaMenu, Producto
from usuarios.models import Usuario

URL = "/api/menu/categorias/"


def crear_usuario(correo, grupo=None, **extra):
    usuario = Usuario.objects.create_user(
        username=correo, email=correo, password="ClaveSegura2026", **extra
    )
    if grupo:
        usuario.groups.add(Group.objects.get_or_create(name=grupo)[0])
    return usuario


def cliente_api(usuario=None):
    api = APIClient()
    if usuario:
        api.force_authenticate(user=usuario)
    return api


@pytest.fixture
def operador(db):
    return cliente_api(crear_usuario("operador@correo.com", "operador"))


@pytest.fixture
def categoria(db):
    return CategoriaMenu.objects.create(nombre="Hamburguesas")


def crear_productos(categoria, cantidad=2):
    return [
        Producto.objects.create(
            categoria=categoria,
            nombre=f"Producto {i}",
            precio_base=15000,
            tiempo_preparacion=10,
        )
        for i in range(cantidad)
    ]


# --- permissions ---

def test_sin_sesion_recibe_401(db):
    assert cliente_api().get(URL).status_code == 401


@pytest.mark.parametrize("grupo", [None, "cliente", "cocina", "repartidor"])
def test_otros_roles_reciben_403(db, grupo):
    api = cliente_api(crear_usuario("otro@correo.com", grupo))
    assert api.get(URL).status_code == 403
    assert api.post(URL, {"nombre": "Postres"}, format="json").status_code == 403


def test_administrador_puede_crear(db):
    api = cliente_api(crear_usuario("admin@correo.com", "administrador"))
    respuesta = api.post(URL, {"nombre": "Postres"}, format="json")
    assert respuesta.status_code == 201


def test_is_staff_puede_crear(db):
    api = cliente_api(crear_usuario("staff@correo.com", is_staff=True))
    assert api.post(URL, {"nombre": "Postres"}, format="json").status_code == 201


# --- create ---

def test_crear_categoria_valida(operador):
    respuesta = operador.post(
        URL, {"nombre": "Pizzas", "descripcion": "Al horno de piedra"}, format="json"
    )
    assert respuesta.status_code == 201
    assert respuesta.data["nombre"] == "Pizzas"
    assert respuesta.data["activa"] is True
    assert respuesta.data["total_productos"] == 0
    assert CategoriaMenu.objects.filter(nombre="Pizzas").exists()


def test_crear_recorta_espacios_del_nombre(operador):
    respuesta = operador.post(URL, {"nombre": "   Pizzas   Grandes  "}, format="json")
    assert respuesta.status_code == 201
    assert respuesta.data["nombre"] == "Pizzas Grandes"


# --- empty name ---

@pytest.mark.parametrize("nombre", ["", "   ", None])
def test_nombre_vacio_es_rechazado(operador, nombre):
    respuesta = operador.post(URL, {"nombre": nombre}, format="json")
    assert respuesta.status_code == 400
    assert "obligatorio" in str(respuesta.data["nombre"])
    assert CategoriaMenu.objects.count() == 0


def test_sin_campo_nombre_es_rechazado(operador):
    respuesta = operador.post(URL, {"descripcion": "Sin nombre"}, format="json")
    assert respuesta.status_code == 400
    assert "obligatorio" in str(respuesta.data["nombre"])


def test_nombre_demasiado_largo_es_rechazado(operador):
    respuesta = operador.post(URL, {"nombre": "A" * 51}, format="json")
    assert respuesta.status_code == 400
    assert "50 caracteres" in str(respuesta.data["nombre"])


# --- duplicated name ---

@pytest.mark.parametrize("nombre", ["Hamburguesas", "hamburguesas", "HAMBURGUESAS", "  Hamburguesas  "])
def test_nombre_duplicado_es_rechazado(operador, categoria, nombre):
    respuesta = operador.post(URL, {"nombre": nombre}, format="json")
    assert respuesta.status_code == 400
    assert "Ya existe" in str(respuesta.data["nombre"])
    assert CategoriaMenu.objects.count() == 1


def test_editar_a_nombre_de_otra_categoria_es_rechazado(operador, categoria):
    otra = CategoriaMenu.objects.create(nombre="Pizzas")
    respuesta = operador.patch(f"{URL}{otra.id}/", {"nombre": "hamburguesas"}, format="json")
    assert respuesta.status_code == 400
    assert "Ya existe" in str(respuesta.data["nombre"])
    otra.refresh_from_db()
    assert otra.nombre == "Pizzas"


def test_editar_conservando_su_propio_nombre_no_cuenta_como_duplicado(operador, categoria):
    respuesta = operador.patch(
        f"{URL}{categoria.id}/",
        {"nombre": "Hamburguesas", "descripcion": "Nueva descripción"},
        format="json",
    )
    assert respuesta.status_code == 200
    categoria.refresh_from_db()
    assert categoria.descripcion == "Nueva descripción"


def test_cambiar_solo_mayusculas_de_su_nombre_esta_permitido(operador, categoria):
    respuesta = operador.patch(f"{URL}{categoria.id}/", {"nombre": "HAMBURGUESAS"}, format="json")
    assert respuesta.status_code == 200
    categoria.refresh_from_db()
    assert categoria.nombre == "HAMBURGUESAS"


# --- edit ---

def test_editar_nombre_vacio_es_rechazado(operador, categoria):
    respuesta = operador.patch(f"{URL}{categoria.id}/", {"nombre": "  "}, format="json")
    assert respuesta.status_code == 400
    categoria.refresh_from_db()
    assert categoria.nombre == "Hamburguesas"


def test_put_sin_nombre_es_rechazado(operador, categoria):
    respuesta = operador.put(f"{URL}{categoria.id}/", {"descripcion": "x"}, format="json")
    assert respuesta.status_code == 400


def test_desactivar_categoria(operador, categoria):
    respuesta = operador.patch(f"{URL}{categoria.id}/", {"activa": False}, format="json")
    assert respuesta.status_code == 200
    categoria.refresh_from_db()
    assert categoria.activa is False


def test_categoria_inexistente_devuelve_404(operador):
    respuesta = operador.patch(f"{URL}99999/", {"nombre": "Nada"}, format="json")
    assert respuesta.status_code == 404


def test_no_se_puede_borrar_categorias(operador, categoria):
    assert operador.delete(f"{URL}{categoria.id}/").status_code == 405
    assert CategoriaMenu.objects.filter(pk=categoria.pk).exists()


# --- rename with products ---

def test_renombrar_mantiene_vinculados_sus_productos(operador, categoria):
    productos = crear_productos(categoria, 2)

    respuesta = operador.patch(f"{URL}{categoria.id}/", {"nombre": "Burgers"}, format="json")

    assert respuesta.status_code == 200
    assert respuesta.data["nombre"] == "Burgers"
    assert respuesta.data["total_productos"] == 2
    categoria.refresh_from_db()
    assert categoria.productos.count() == 2
    for producto in productos:
        producto.refresh_from_db()
        assert producto.categoria_id == categoria.id
        assert producto.categoria.nombre == "Burgers"


def test_renombrar_no_toca_los_productos_de_otras_categorias(operador, categoria):
    otra = CategoriaMenu.objects.create(nombre="Pizzas")
    crear_productos(categoria, 2)
    crear_productos(otra, 3)

    operador.patch(f"{URL}{categoria.id}/", {"nombre": "Burgers"}, format="json")

    assert categoria.productos.count() == 2
    assert otra.productos.count() == 3


# --- list ---

def test_listar_ordenado_con_total_de_productos(operador, categoria):
    pizzas = CategoriaMenu.objects.create(nombre="Pizzas")
    CategoriaMenu.objects.create(nombre="Bebidas")
    crear_productos(categoria, 2)
    crear_productos(pizzas, 1)

    respuesta = operador.get(URL)

    assert respuesta.status_code == 200
    resumen = [(c["nombre"], c["total_productos"]) for c in respuesta.data]
    assert resumen == [("Bebidas", 0), ("Hamburguesas", 2), ("Pizzas", 1)]


def test_detalle_de_una_categoria(operador, categoria):
    crear_productos(categoria, 1)
    respuesta = operador.get(f"{URL}{categoria.id}/")
    assert respuesta.status_code == 200
    assert respuesta.data["total_productos"] == 1
