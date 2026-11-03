"""Pruebas de HU-77 · Ingredientes de un producto (SCRUM-34)."""
from decimal import Decimal

import pytest
from django.contrib.auth.models import Group
from rest_framework.test import APIClient

from menu.models import CategoriaMenu, Insumo, Producto, ProductoInsumo
from pedidos.models import DetallePedido, Pedido
from sedes.models import Ciudad, Sede
from usuarios.models import Usuario

pytestmark = pytest.mark.django_db

URL_INSUMOS = "/api/menu/insumos/"
CLAVE = "ClaveSegura#2026"


def crear_usuario(email, rol=None):
    usuario = Usuario.objects.create_user(username=email, email=email, password=CLAVE)
    if rol:
        usuario.groups.add(Group.objects.get_or_create(name=rol)[0])
    return usuario


def cliente_api(usuario=None):
    api = APIClient()
    if usuario:
        api.force_authenticate(usuario)
    return api


def url_ingredientes(producto):
    return f"/api/menu/productos/{producto.id}/ingredientes/"


@pytest.fixture
def api_operador():
    return cliente_api(crear_usuario("operador@correo.com", "operador"))


@pytest.fixture
def cebolla():
    return Insumo.objects.create(nombre="Cebolla", unidad_medida="g")


@pytest.fixture
def producto():
    categoria = CategoriaMenu.objects.create(nombre="Hamburguesas")
    return Producto.objects.create(
        categoria=categoria, nombre="Clásica", precio_base=15000, tiempo_preparacion=15
    )


# --- Catálogo de ingredientes (insumos) ------------------------------------------


def test_operador_registra_ingrediente(api_operador):
    respuesta = api_operador.post(
        URL_INSUMOS, {"nombre": "Lechuga", "unidad_medida": "g"}, format="json"
    )

    assert respuesta.status_code == 201
    assert respuesta.data["nombre"] == "Lechuga"
    assert respuesta.data["activo"] is True


# Criterio 4: no se guardan ingredientes con el nombre en blanco.
@pytest.mark.parametrize("nombre", ["", "   "])
def test_nombre_en_blanco_es_rechazado(api_operador, nombre):
    respuesta = api_operador.post(
        URL_INSUMOS, {"nombre": nombre, "unidad_medida": "g"}, format="json"
    )

    assert respuesta.status_code == 400
    assert "nombre" in respuesta.data
    assert not Insumo.objects.exists()


def test_nombre_repetido_es_rechazado(api_operador, cebolla):
    respuesta = api_operador.post(
        URL_INSUMOS, {"nombre": "CEBOLLA", "unidad_medida": "g"}, format="json"
    )

    assert respuesta.status_code == 400
    assert "nombre" in respuesta.data


def test_nombre_de_ingrediente_eliminado_sugiere_restaurar(api_operador, cebolla):
    cebolla.activo = False
    cebolla.save()
    respuesta = api_operador.post(
        URL_INSUMOS, {"nombre": "Cebolla", "unidad_medida": "g"}, format="json"
    )

    assert respuesta.status_code == 400
    assert "Restáuralo" in str(respuesta.data["nombre"])


def test_unidad_invalida_es_rechazada(api_operador):
    respuesta = api_operador.post(
        URL_INSUMOS, {"nombre": "Sal", "unidad_medida": "cucharada"}, format="json"
    )

    assert respuesta.status_code == 400
    assert "unidad_medida" in respuesta.data


def test_operador_edita_ingrediente(api_operador, cebolla):
    respuesta = api_operador.patch(
        f"{URL_INSUMOS}{cebolla.id}/", {"nombre": "Cebolla morada"}, format="json"
    )

    assert respuesta.status_code == 200
    cebolla.refresh_from_db()
    assert cebolla.nombre == "Cebolla morada"


def test_eliminar_ingrediente_es_borrado_logico(api_operador, cebolla):
    respuesta = api_operador.delete(f"{URL_INSUMOS}{cebolla.id}/")

    assert respuesta.status_code == 204
    cebolla.refresh_from_db()
    assert cebolla.activo is False

    activos = api_operador.get(URL_INSUMOS)
    assert cebolla.id not in [i["id"] for i in activos.data]
    todos = api_operador.get(URL_INSUMOS, {"activo": "todos"})
    assert cebolla.id in [i["id"] for i in todos.data]


def test_ingrediente_eliminado_se_puede_restaurar(api_operador, cebolla):
    api_operador.delete(f"{URL_INSUMOS}{cebolla.id}/")
    respuesta = api_operador.patch(f"{URL_INSUMOS}{cebolla.id}/", {"activo": True}, format="json")

    assert respuesta.status_code == 200
    cebolla.refresh_from_db()
    assert cebolla.activo is True


# --- Ingredientes de un producto ---------------------------------------------------


# Criterio 1: el operador registra la lista de ingredientes de un plato.
def test_agregar_ingrediente_a_producto(api_operador, producto, cebolla):
    respuesta = api_operador.post(
        url_ingredientes(producto),
        {"insumo": cebolla.id, "cantidad_necesaria": "10", "es_excluible": True},
        format="json",
    )

    assert respuesta.status_code == 201
    assert respuesta.data["insumo_nombre"] == "Cebolla"
    assert respuesta.data["es_excluible"] is True

    lista = api_operador.get(url_ingredientes(producto))
    assert [i["insumo"] for i in lista.data] == [cebolla.id]


# Criterio 2: si no se marca la casilla, el ingrediente no se puede quitar.
def test_por_defecto_el_ingrediente_no_es_excluible(api_operador, producto, cebolla):
    respuesta = api_operador.post(
        url_ingredientes(producto), {"insumo": cebolla.id, "cantidad_necesaria": "10"}, format="json"
    )

    assert respuesta.status_code == 201
    assert respuesta.data["es_excluible"] is False


def test_marcar_ingrediente_como_excluible(api_operador, producto, cebolla):
    vinculo = ProductoInsumo.objects.create(
        producto=producto, insumo=cebolla, cantidad_necesaria=Decimal("10")
    )
    respuesta = api_operador.patch(
        f"{url_ingredientes(producto)}{vinculo.id}/", {"es_excluible": True}, format="json"
    )

    assert respuesta.status_code == 200
    vinculo.refresh_from_db()
    assert vinculo.es_excluible is True


def test_cantidad_debe_ser_mayor_que_cero(api_operador, producto, cebolla):
    respuesta = api_operador.post(
        url_ingredientes(producto), {"insumo": cebolla.id, "cantidad_necesaria": "0"}, format="json"
    )

    assert respuesta.status_code == 400
    assert "cantidad_necesaria" in respuesta.data


def test_no_se_repite_un_ingrediente_en_el_producto(api_operador, producto, cebolla):
    datos = {"insumo": cebolla.id, "cantidad_necesaria": "10"}
    api_operador.post(url_ingredientes(producto), datos, format="json")
    respuesta = api_operador.post(url_ingredientes(producto), datos, format="json")

    assert respuesta.status_code == 400
    assert "insumo" in respuesta.data


def test_no_se_agrega_un_ingrediente_eliminado(api_operador, producto, cebolla):
    cebolla.activo = False
    cebolla.save()
    respuesta = api_operador.post(
        url_ingredientes(producto), {"insumo": cebolla.id, "cantidad_necesaria": "10"}, format="json"
    )

    assert respuesta.status_code == 400


def test_quitar_ingrediente_del_producto(api_operador, producto, cebolla):
    vinculo = ProductoInsumo.objects.create(
        producto=producto, insumo=cebolla, cantidad_necesaria=Decimal("10")
    )
    respuesta = api_operador.delete(f"{url_ingredientes(producto)}{vinculo.id}/")

    assert respuesta.status_code == 204
    assert not ProductoInsumo.objects.filter(pk=vinculo.pk).exists()
    assert Insumo.objects.filter(pk=cebolla.pk, activo=True).exists()


# Criterio 3: modificar o borrar ingredientes no altera los pedidos previos.
def test_cambiar_ingredientes_no_altera_pedidos_previos(api_operador, producto, cebolla):
    ciudad = Ciudad.objects.create(nombre="Cali")
    sede = Sede.objects.create(
        ciudad=ciudad, nombre="Sede Centro", direccion="Cra 1 # 2-3", latitud=3.45,
        longitud=-76.53, barrio="Centro", telefono="3000000000", correo="centro@domi.com",
    )
    pedido = Pedido.objects.create(sede=sede, numero_pedido="P-200")
    detalle = DetallePedido.objects.create(
        pedido=pedido, producto=producto, cantidad=2, precio_unitario=15000,
        subtotal=30000, observaciones="Sin cebolla",
    )
    vinculo = ProductoInsumo.objects.create(
        producto=producto, insumo=cebolla, cantidad_necesaria=Decimal("10"), es_excluible=True
    )

    url = f"{url_ingredientes(producto)}{vinculo.id}/"
    api_operador.patch(url, {"es_excluible": False, "cantidad_necesaria": "20"}, format="json")
    api_operador.delete(url)

    detalle.refresh_from_db()
    assert detalle.producto_id == producto.id
    assert detalle.cantidad == 2
    assert detalle.precio_unitario == Decimal("15000")
    assert detalle.observaciones == "Sin cebolla"


def test_producto_inexistente_responde_404(api_operador):
    assert api_operador.get("/api/menu/productos/9999/ingredientes/").status_code == 404


# --- Permisos ----------------------------------------------------------------------


def test_sin_sesion_responde_401():
    assert cliente_api().get(URL_INSUMOS).status_code == 401


def test_cliente_no_puede_gestionar_ingredientes(producto):
    api = cliente_api(crear_usuario("cliente@correo.com", "cliente"))

    assert api.get(URL_INSUMOS).status_code == 403
    assert api.get(url_ingredientes(producto)).status_code == 403
