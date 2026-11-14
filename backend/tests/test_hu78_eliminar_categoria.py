"""HU-78: delete menu categories."""
import pytest
from django.contrib.auth.models import Group
from django.db.models import ProtectedError
from rest_framework.test import APIClient

from menu.models import CategoriaMenu, Producto
from usuarios.models import Usuario

URL = "/api/menu/categorias/"

pytestmark = pytest.mark.django_db


def _usuario(correo, grupo=None):
    usuario = Usuario.objects.create_user(username=correo, email=correo, password="ClaveSegura2026")
    if grupo:
        usuario.groups.add(Group.objects.get_or_create(name=grupo)[0])
    return usuario


def _api(usuario=None):
    api = APIClient()
    if usuario:
        api.force_authenticate(user=usuario)
    return api


def _producto(categoria, nombre="Producto", activo=True):
    return Producto.objects.create(
        categoria=categoria, nombre=nombre, precio_base=15000, tiempo_preparacion=10, activo=activo
    )


@pytest.fixture
def operador():
    return _api(_usuario("operador@correo.com", "operador"))


@pytest.fixture
def categoria():
    return CategoriaMenu.objects.create(nombre="Hamburguesas")


# --- Criterio 1 (el modal es del frontend): la categoría vacía se elimina --------

def test_elimina_una_categoria_sin_productos(operador, categoria):
    respuesta = operador.delete(f"{URL}{categoria.id}/")

    assert respuesta.status_code == 204
    assert not CategoriaMenu.objects.filter(pk=categoria.pk).exists()
    assert categoria.id not in [c["id"] for c in operador.get(URL).data]


def test_eliminar_una_no_afecta_a_las_demas(operador, categoria):
    otra = CategoriaMenu.objects.create(nombre="Bebidas")
    producto = _producto(otra)

    assert operador.delete(f"{URL}{categoria.id}/").status_code == 204

    assert CategoriaMenu.objects.filter(pk=otra.pk).exists()
    assert Producto.objects.filter(pk=producto.pk, categoria=otra).exists()


def test_la_categoria_eliminada_ya_no_existe(operador, categoria):
    operador.delete(f"{URL}{categoria.id}/")

    assert operador.delete(f"{URL}{categoria.id}/").status_code == 404
    assert operador.get(f"{URL}{categoria.id}/").status_code == 404


# --- Criterio 2: bloquea si tiene productos asociados -----------------------------

def test_bloquea_si_tiene_productos(operador, categoria):
    _producto(categoria, "Sencilla")
    _producto(categoria, "Doble")

    respuesta = operador.delete(f"{URL}{categoria.id}/")

    assert respuesta.status_code == 409
    assert respuesta.data["codigo"] == "categoria_con_productos"
    assert respuesta.data["total_productos"] == 2
    assert "2 productos asociados" in respuesta.data["detail"]
    assert CategoriaMenu.objects.filter(pk=categoria.pk).exists()
    assert Producto.objects.filter(categoria=categoria).count() == 2


def test_el_mensaje_va_en_singular_con_un_producto(operador, categoria):
    _producto(categoria)

    respuesta = operador.delete(f"{URL}{categoria.id}/")

    assert "1 producto asociado" in respuesta.data["detail"]


def test_los_productos_inactivos_tambien_bloquean(operador, categoria):
    _producto(categoria, "Retirado", activo=False)

    respuesta = operador.delete(f"{URL}{categoria.id}/")

    assert respuesta.status_code == 409
    assert respuesta.data["total_productos"] == 1
    assert CategoriaMenu.objects.filter(pk=categoria.pk).exists()


def test_se_desbloquea_al_mover_los_productos_a_otra_categoria(operador, categoria):
    otra = CategoriaMenu.objects.create(nombre="Bebidas")
    producto = _producto(categoria)
    assert operador.delete(f"{URL}{categoria.id}/").status_code == 409

    producto.categoria = otra
    producto.save()

    assert operador.delete(f"{URL}{categoria.id}/").status_code == 204
    assert Producto.objects.filter(pk=producto.pk, categoria=otra).exists()


def test_si_aparece_un_producto_justo_al_borrar_la_base_de_datos_tambien_bloquea(
    operador, categoria, monkeypatch
):
    # the count at the start finds no products (this category is empty) and then
    # the database refuses the delete, as when a product is added at that moment
    def borrado_protegido(self, *args, **kwargs):
        raise ProtectedError("hay productos", set())

    monkeypatch.setattr(CategoriaMenu, "delete", borrado_protegido)

    respuesta = operador.delete(f"{URL}{categoria.id}/")

    assert respuesta.status_code == 409
    assert respuesta.data["codigo"] == "categoria_con_productos"
    assert CategoriaMenu.objects.filter(pk=categoria.pk).exists()


# --- Permisos --------------------------------------------------------------------

def test_sin_sesion_recibe_401(categoria):
    assert _api().delete(f"{URL}{categoria.id}/").status_code == 401
    assert CategoriaMenu.objects.filter(pk=categoria.pk).exists()


@pytest.mark.parametrize("grupo", [None, "cliente", "cocina", "repartidor"])
def test_otros_roles_reciben_403(categoria, grupo):
    api = _api(_usuario("otro@correo.com", grupo))

    assert api.delete(f"{URL}{categoria.id}/").status_code == 403
    assert CategoriaMenu.objects.filter(pk=categoria.pk).exists()


def test_el_administrador_tambien_puede_eliminar(categoria):
    api = _api(_usuario("admin@correo.com", "administrador"))

    assert api.delete(f"{URL}{categoria.id}/").status_code == 204
