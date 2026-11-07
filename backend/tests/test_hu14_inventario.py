"""HU-14 · Registrar y actualizar existencias (productos e ingredientes) por sede."""
from decimal import Decimal

import pytest
from django.contrib.auth.models import Group
from rest_framework.test import APIClient

from inventario.models import InventarioInsumo, InventarioProducto
from menu.models import CategoriaMenu, Insumo, Producto
from sedes.models import Ciudad, Sede
from usuarios.models import Empleado, Usuario

URL_PRODUCTOS = "/api/inventario/productos/"
URL_INSUMOS = "/api/inventario/insumos/"


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
def producto(db):
    categoria = CategoriaMenu.objects.create(nombre="Hamburguesas")
    return Producto.objects.create(
        categoria=categoria, nombre="Clásica", precio_base=Decimal("18000"),
        tiempo_preparacion=15, tipo_control_stock=Producto.TipoControlStock.PRODUCTO,
    )


@pytest.fixture
def otro_producto(db):
    categoria = CategoriaMenu.objects.get_or_create(nombre="Hamburguesas")[0]
    return Producto.objects.create(
        categoria=categoria, nombre="Doble", precio_base=Decimal("24000"), tiempo_preparacion=15
    )


@pytest.fixture
def queso(db):
    return Insumo.objects.create(nombre="Queso", unidad_medida="kg")


@pytest.fixture
def operador_centro(centro):
    return api_de(crear_usuario("op.centro@correo.com", "operador", centro, "101"))


@pytest.fixture
def administrador(db):
    return api_de(crear_usuario("admin@correo.com", "administrador"))


# --- permissions ---


def test_sin_sesion_recibe_401(db):
    assert api_de().get(URL_PRODUCTOS).status_code == 401
    assert api_de().get(URL_INSUMOS).status_code == 401


@pytest.mark.parametrize("grupo", ["cliente", "cocina", "repartidor"])
def test_otros_roles_reciben_403(centro, grupo):
    api = api_de(crear_usuario("otro@correo.com", grupo, centro))
    assert api.get(URL_PRODUCTOS).status_code == 403
    assert api.get(URL_INSUMOS).status_code == 403


def test_operador_sin_sede_no_puede_registrar(db, producto):
    api = api_de(crear_usuario("sinsede@correo.com", "operador"))
    assert api.get(URL_PRODUCTOS).data == []
    respuesta = api.post(URL_PRODUCTOS, {"producto": producto.id, "stock_actual": 5}, format="json")
    assert respuesta.status_code == 403


# --- product stock: create ---


def test_operador_registra_existencias_en_su_sede(operador_centro, producto, centro):
    respuesta = operador_centro.post(
        URL_PRODUCTOS, {"producto": producto.id, "stock_actual": 20, "stock_minimo": 5}, format="json"
    )
    assert respuesta.status_code == 201
    assert respuesta.data["sede"] == centro.id
    assert respuesta.data["sede_nombre"] == "Centro"
    assert respuesta.data["producto_nombre"] == "Clásica"
    assert respuesta.data["categoria_nombre"] == "Hamburguesas"
    assert respuesta.data["stock_actual"] == 20
    assert respuesta.data["stock_minimo"] == 5
    registro = InventarioProducto.objects.get(sede=centro, producto=producto)
    assert registro.stock_actual == 20


def test_stock_minimo_es_opcional_y_queda_en_cero(operador_centro, producto):
    respuesta = operador_centro.post(URL_PRODUCTOS, {"producto": producto.id, "stock_actual": 3}, format="json")
    assert respuesta.status_code == 201
    assert respuesta.data["stock_minimo"] == 0


def test_operador_puede_indicar_su_propia_sede(operador_centro, producto, centro):
    respuesta = operador_centro.post(
        URL_PRODUCTOS, {"sede": centro.id, "producto": producto.id, "stock_actual": 1}, format="json"
    )
    assert respuesta.status_code == 201


def test_operador_no_puede_registrar_en_otra_sede(operador_centro, producto, sur):
    respuesta = operador_centro.post(
        URL_PRODUCTOS, {"sede": sur.id, "producto": producto.id, "stock_actual": 1}, format="json"
    )
    assert respuesta.status_code == 403
    assert not InventarioProducto.objects.filter(sede=sur).exists()


def test_administrador_debe_indicar_la_sede(administrador, producto, sur):
    sin_sede = administrador.post(URL_PRODUCTOS, {"producto": producto.id, "stock_actual": 4}, format="json")
    assert sin_sede.status_code == 400
    assert "Indica la sede" in str(sin_sede.data["sede"])

    con_sede = administrador.post(
        URL_PRODUCTOS, {"sede": sur.id, "producto": producto.id, "stock_actual": 4}, format="json"
    )
    assert con_sede.status_code == 201
    assert con_sede.data["sede"] == sur.id


def test_no_se_registra_dos_veces_el_mismo_producto_en_la_sede(operador_centro, producto, centro):
    InventarioProducto.objects.create(sede=centro, producto=producto, stock_actual=7)
    respuesta = operador_centro.post(URL_PRODUCTOS, {"producto": producto.id, "stock_actual": 9}, format="json")
    assert respuesta.status_code == 400
    assert "ya tiene existencias" in str(respuesta.data["producto"])
    assert InventarioProducto.objects.get(sede=centro, producto=producto).stock_actual == 7


def test_el_mismo_producto_puede_estar_en_dos_sedes(administrador, producto, centro, sur):
    for sede in (centro, sur):
        respuesta = administrador.post(
            URL_PRODUCTOS, {"sede": sede.id, "producto": producto.id, "stock_actual": 2}, format="json"
        )
        assert respuesta.status_code == 201


def test_producto_es_obligatorio(operador_centro):
    respuesta = operador_centro.post(URL_PRODUCTOS, {"stock_actual": 5}, format="json")
    assert respuesta.status_code == 400
    assert "Selecciona el producto" in str(respuesta.data["producto"])


def test_producto_inactivo_o_inexistente_es_rechazado(operador_centro, producto):
    producto.activo = False
    producto.save()
    inactivo = operador_centro.post(URL_PRODUCTOS, {"producto": producto.id, "stock_actual": 5}, format="json")
    assert inactivo.status_code == 400
    assert "inactivo" in str(inactivo.data["producto"])

    inexistente = operador_centro.post(URL_PRODUCTOS, {"producto": 99999, "stock_actual": 5}, format="json")
    assert inexistente.status_code == 400


def test_stock_actual_es_obligatorio(operador_centro, producto):
    respuesta = operador_centro.post(URL_PRODUCTOS, {"producto": producto.id}, format="json")
    assert respuesta.status_code == 400
    assert "obligatorio" in str(respuesta.data["stock_actual"])


@pytest.mark.parametrize(
    "valor, texto",
    [(-1, "negativo"), (1.5, "entero"), ("abc", "entero"), (2_147_483_648, "demasiado grande")],
)
def test_stock_actual_invalido_es_rechazado(operador_centro, producto, valor, texto):
    respuesta = operador_centro.post(URL_PRODUCTOS, {"producto": producto.id, "stock_actual": valor}, format="json")
    assert respuesta.status_code == 400
    assert texto in str(respuesta.data["stock_actual"])


def test_stock_minimo_negativo_es_rechazado(operador_centro, producto):
    respuesta = operador_centro.post(
        URL_PRODUCTOS, {"producto": producto.id, "stock_actual": 5, "stock_minimo": -2}, format="json"
    )
    assert respuesta.status_code == 400
    assert "negativo" in str(respuesta.data["stock_minimo"])


# --- product stock: list ---


def test_operador_solo_ve_las_existencias_de_su_sede(operador_centro, producto, otro_producto, centro, sur):
    InventarioProducto.objects.create(sede=centro, producto=producto, stock_actual=5)
    InventarioProducto.objects.create(sede=sur, producto=producto, stock_actual=9)
    InventarioProducto.objects.create(sede=centro, producto=otro_producto, stock_actual=2)

    respuesta = operador_centro.get(URL_PRODUCTOS)

    assert respuesta.status_code == 200
    resumen = [(f["producto_nombre"], f["sede_nombre"], f["stock_actual"]) for f in respuesta.data]
    assert resumen == [("Clásica", "Centro", 5), ("Doble", "Centro", 2)]


def test_operador_no_puede_ver_otra_sede_con_el_filtro(operador_centro, producto, sur):
    InventarioProducto.objects.create(sede=sur, producto=producto, stock_actual=9)
    assert operador_centro.get(f"{URL_PRODUCTOS}?sede={sur.id}").data == []


def test_administrador_ve_todo_y_puede_filtrar_por_sede(administrador, producto, centro, sur):
    InventarioProducto.objects.create(sede=centro, producto=producto, stock_actual=5)
    InventarioProducto.objects.create(sede=sur, producto=producto, stock_actual=9)

    assert len(administrador.get(URL_PRODUCTOS).data) == 2
    solo_sur = administrador.get(f"{URL_PRODUCTOS}?sede={sur.id}").data
    assert [f["sede_nombre"] for f in solo_sur] == ["Sur"]


def test_filtro_de_sede_no_numerico_es_rechazado(administrador):
    respuesta = administrador.get(f"{URL_PRODUCTOS}?sede=abc")
    assert respuesta.status_code == 400
    assert "id numérico" in str(respuesta.data["sede"])


# --- product stock: update ---


def test_operador_ajusta_el_stock(operador_centro, producto, centro):
    registro = InventarioProducto.objects.create(sede=centro, producto=producto, stock_actual=5, stock_minimo=2)
    respuesta = operador_centro.patch(f"{URL_PRODUCTOS}{registro.id}/", {"stock_actual": 40}, format="json")
    assert respuesta.status_code == 200
    assert respuesta.data["stock_actual"] == 40
    registro.refresh_from_db()
    assert registro.stock_actual == 40
    assert registro.stock_minimo == 2


def test_ajustar_una_sede_no_cambia_las_otras(operador_centro, producto, centro, sur):
    registro = InventarioProducto.objects.create(sede=centro, producto=producto, stock_actual=5)
    otra = InventarioProducto.objects.create(sede=sur, producto=producto, stock_actual=8)
    operador_centro.patch(f"{URL_PRODUCTOS}{registro.id}/", {"stock_actual": 0}, format="json")
    otra.refresh_from_db()
    assert otra.stock_actual == 8


def test_se_puede_dejar_el_stock_en_cero(operador_centro, producto, centro):
    registro = InventarioProducto.objects.create(sede=centro, producto=producto, stock_actual=5)
    respuesta = operador_centro.patch(f"{URL_PRODUCTOS}{registro.id}/", {"stock_actual": 0}, format="json")
    assert respuesta.status_code == 200
    registro.refresh_from_db()
    assert registro.stock_actual == 0


def test_ajuste_invalido_no_modifica_el_registro(operador_centro, producto, centro):
    registro = InventarioProducto.objects.create(sede=centro, producto=producto, stock_actual=5)
    respuesta = operador_centro.patch(f"{URL_PRODUCTOS}{registro.id}/", {"stock_actual": -3}, format="json")
    assert respuesta.status_code == 400
    registro.refresh_from_db()
    assert registro.stock_actual == 5


def test_operador_no_puede_ajustar_otra_sede(operador_centro, producto, sur):
    registro = InventarioProducto.objects.create(sede=sur, producto=producto, stock_actual=5)
    assert operador_centro.patch(f"{URL_PRODUCTOS}{registro.id}/", {"stock_actual": 1}, format="json").status_code == 404
    assert operador_centro.get(f"{URL_PRODUCTOS}{registro.id}/").status_code == 404
    assert operador_centro.delete(f"{URL_PRODUCTOS}{registro.id}/").status_code == 404
    registro.refresh_from_db()
    assert registro.stock_actual == 5


def test_administrador_puede_ajustar_cualquier_sede(administrador, producto, sur):
    registro = InventarioProducto.objects.create(sede=sur, producto=producto, stock_actual=5)
    respuesta = administrador.patch(f"{URL_PRODUCTOS}{registro.id}/", {"stock_actual": 11}, format="json")
    assert respuesta.status_code == 200
    registro.refresh_from_db()
    assert registro.stock_actual == 11


def test_put_pide_el_stock_actual(operador_centro, producto, centro):
    registro = InventarioProducto.objects.create(sede=centro, producto=producto, stock_actual=5)
    sin_stock = operador_centro.put(f"{URL_PRODUCTOS}{registro.id}/", {"producto": producto.id}, format="json")
    assert sin_stock.status_code == 400

    completo = operador_centro.put(
        f"{URL_PRODUCTOS}{registro.id}/",
        {"producto": producto.id, "stock_actual": 12, "stock_minimo": 4},
        format="json",
    )
    assert completo.status_code == 200
    registro.refresh_from_db()
    assert (registro.stock_actual, registro.stock_minimo) == (12, 4)


def test_no_se_puede_cambiar_el_producto_ni_la_sede(operador_centro, producto, otro_producto, centro, sur):
    registro = InventarioProducto.objects.create(sede=centro, producto=producto, stock_actual=5)
    cambia_producto = operador_centro.patch(
        f"{URL_PRODUCTOS}{registro.id}/", {"producto": otro_producto.id}, format="json"
    )
    assert cambia_producto.status_code == 400
    assert "No se puede cambiar" in str(cambia_producto.data["producto"])

    cambia_sede = operador_centro.patch(f"{URL_PRODUCTOS}{registro.id}/", {"sede": sur.id}, format="json")
    assert cambia_sede.status_code == 400
    registro.refresh_from_db()
    assert (registro.sede_id, registro.producto_id) == (centro.id, producto.id)


def test_disponible_no_se_cambia_desde_las_existencias(operador_centro, producto, centro):
    registro = InventarioProducto.objects.create(sede=centro, producto=producto, stock_actual=5, disponible=True)
    operador_centro.patch(f"{URL_PRODUCTOS}{registro.id}/", {"disponible": False}, format="json")
    registro.refresh_from_db()
    assert registro.disponible is True


# --- product stock: delete ---


def test_operador_quita_las_existencias_de_su_sede(operador_centro, producto, centro):
    registro = InventarioProducto.objects.create(sede=centro, producto=producto, stock_actual=5)
    assert operador_centro.delete(f"{URL_PRODUCTOS}{registro.id}/").status_code == 204
    assert not InventarioProducto.objects.filter(pk=registro.pk).exists()
    assert disponible_en_menu(centro, producto) is False


# --- reflected for the client ---


def test_el_menu_del_cliente_refleja_el_ajuste_de_stock(operador_centro, producto, centro):
    registro = InventarioProducto.objects.create(sede=centro, producto=producto, stock_actual=3, disponible=True)
    assert disponible_en_menu(centro, producto) is True

    operador_centro.patch(f"{URL_PRODUCTOS}{registro.id}/", {"stock_actual": 0}, format="json")
    assert disponible_en_menu(centro, producto) is False

    operador_centro.patch(f"{URL_PRODUCTOS}{registro.id}/", {"stock_actual": 12}, format="json")
    assert disponible_en_menu(centro, producto) is True


def test_registrar_existencias_deja_el_producto_disponible_en_la_sede(operador_centro, producto, centro):
    operador_centro.post(URL_PRODUCTOS, {"producto": producto.id, "stock_actual": 6}, format="json")
    assert disponible_en_menu(centro, producto) is True


# --- ingredient stock ---


def test_operador_registra_existencias_de_un_ingrediente(operador_centro, queso, centro):
    respuesta = operador_centro.post(
        URL_INSUMOS, {"insumo": queso.id, "stock_actual": "12.500", "stock_minimo": "2"}, format="json"
    )
    assert respuesta.status_code == 201
    assert respuesta.data["insumo_nombre"] == "Queso"
    assert respuesta.data["unidad_medida"] == "kg"
    assert respuesta.data["sede"] == centro.id
    registro = InventarioInsumo.objects.get(sede=centro, insumo=queso)
    assert registro.stock_actual == Decimal("12.500")
    assert registro.stock_minimo == Decimal("2")


def test_ingrediente_duplicado_en_la_sede_es_rechazado(operador_centro, queso, centro):
    InventarioInsumo.objects.create(sede=centro, insumo=queso, stock_actual=1)
    respuesta = operador_centro.post(URL_INSUMOS, {"insumo": queso.id, "stock_actual": "3"}, format="json")
    assert respuesta.status_code == 400
    assert "ya tiene existencias" in str(respuesta.data["insumo"])


@pytest.mark.parametrize(
    "valor, texto",
    [("-0.5", "negativo"), ("abc", "número válido"), ("1.2345", "3 decimales"), ("1000000000", "demasiado grande")],
)
def test_stock_de_ingrediente_invalido_es_rechazado(operador_centro, queso, valor, texto):
    respuesta = operador_centro.post(URL_INSUMOS, {"insumo": queso.id, "stock_actual": valor}, format="json")
    assert respuesta.status_code == 400
    assert texto in str(respuesta.data["stock_actual"])


def test_ingrediente_inactivo_es_rechazado(operador_centro, queso):
    queso.activo = False
    queso.save()
    respuesta = operador_centro.post(URL_INSUMOS, {"insumo": queso.id, "stock_actual": "3"}, format="json")
    assert respuesta.status_code == 400
    assert "inactivo" in str(respuesta.data["insumo"])


def test_ajustar_y_quitar_existencias_de_un_ingrediente(operador_centro, queso, centro):
    registro = InventarioInsumo.objects.create(sede=centro, insumo=queso, stock_actual=Decimal("5"))
    ajuste = operador_centro.patch(f"{URL_INSUMOS}{registro.id}/", {"stock_actual": "7.250"}, format="json")
    assert ajuste.status_code == 200
    registro.refresh_from_db()
    assert registro.stock_actual == Decimal("7.250")

    assert operador_centro.delete(f"{URL_INSUMOS}{registro.id}/").status_code == 204
    assert not InventarioInsumo.objects.filter(pk=registro.pk).exists()


def test_operador_solo_ve_y_toca_ingredientes_de_su_sede(operador_centro, queso, centro, sur):
    propio = InventarioInsumo.objects.create(sede=centro, insumo=queso, stock_actual=1)
    ajeno = InventarioInsumo.objects.create(sede=sur, insumo=queso, stock_actual=2)

    visibles = [fila["id"] for fila in operador_centro.get(URL_INSUMOS).data]
    assert visibles == [propio.id]
    assert operador_centro.patch(f"{URL_INSUMOS}{ajeno.id}/", {"stock_actual": "9"}, format="json").status_code == 404
