"""HU-11 · Productos del menú: crear, editar, validar e imagen."""
import io
from decimal import Decimal

import pytest
from django.contrib.auth.models import Group
from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image
from rest_framework.test import APIClient

from inventario.models import InventarioProducto
from menu import serializers as menu_serializers
from menu.models import CategoriaMenu, Producto
from pedidos.models import DetallePedido, Pedido
from sedes.models import Ciudad, Sede
from usuarios.models import Usuario

URL = "/api/menu/productos/"


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


def crear_imagen(formato="PNG", nombre="foto.png", tipo="image/png"):
    buffer = io.BytesIO()
    Image.new("RGB", (40, 40), color=(200, 30, 30)).save(buffer, format=formato)
    return SimpleUploadedFile(nombre, buffer.getvalue(), content_type=tipo)


def crear_sede(nombre, activa=True):
    ciudad, _ = Ciudad.objects.get_or_create(nombre="Cali")
    return Sede.objects.create(
        ciudad=ciudad, nombre=nombre, direccion="Cra 1 # 2-3", activa=activa,
        latitud=3.45, longitud=-76.53, barrio="Centro",
        telefono="3000000000", correo=f"{nombre.lower().replace(' ', '')}@domi.com",
    )


@pytest.fixture(autouse=True)
def media_temporal(settings, tmp_path):
    # Test images go to a temp folder, not to the project
    settings.MEDIA_ROOT = tmp_path


@pytest.fixture
def operador(db):
    return cliente_api(crear_usuario("operador@correo.com", "operador"))


@pytest.fixture
def categoria(db):
    return CategoriaMenu.objects.create(nombre="Hamburguesas")


@pytest.fixture
def sede(db):
    return crear_sede("Sede Centro")


@pytest.fixture
def datos(categoria, sede):
    return {
        "nombre": "Clásica",
        "descripcion": "Carne, queso y tomate",
        "precio_base": "15000",
        "tiempo_preparacion": 12,
        "categoria": categoria.id,
        "sedes": [sede.id],
    }


@pytest.fixture
def producto(categoria, sede):
    producto = Producto.objects.create(
        categoria=categoria, nombre="Clásica", precio_base=15000, tiempo_preparacion=10,
    )
    InventarioProducto.objects.create(sede=sede, producto=producto, disponible=True)
    return producto


def menu_cliente(sede):
    """Products the client sees in the sede menu (public endpoint of HU-18)"""
    respuesta = APIClient().get(f"/api/menu/sedes/{sede.id}/menu/")
    assert respuesta.status_code == 200
    return {p["id"]: p for c in respuesta.data["categorias"] for p in c["productos"]}


# --- permisos ---

def test_sin_sesion_recibe_401(db):
    assert cliente_api().get(URL).status_code == 401


@pytest.mark.parametrize("grupo", [None, "cliente", "cocina", "repartidor"])
def test_otros_roles_reciben_403(db, grupo, datos):
    api = cliente_api(crear_usuario("otro@correo.com", grupo))
    assert api.get(URL).status_code == 403
    assert api.post(URL, datos, format="json").status_code == 403


def test_administrador_puede_crear(db, datos):
    api = cliente_api(crear_usuario("admin@correo.com", "administrador"))
    assert api.post(URL, datos, format="json").status_code == 201


# --- crear ---

def test_crea_producto_con_imagen_y_sede(operador, datos, sede):
    respuesta = operador.post(URL, {**datos, "imagen": crear_imagen()}, format="multipart")

    assert respuesta.status_code == 201, respuesta.data
    producto = Producto.objects.get(pk=respuesta.data["id"])
    assert producto.precio_base == Decimal("15000")
    assert producto.tiempo_preparacion == 12
    assert producto.imagen.name.startswith("productos/")
    assert producto.imagen.storage.exists(producto.imagen.name)
    assert respuesta.data["imagen"].endswith(producto.imagen.name)
    assert respuesta.data["sedes"] == [sede.id]
    assert respuesta.data["categoria_nombre"] == "Hamburguesas"
    assert InventarioProducto.objects.get(producto=producto, sede=sede).disponible


def test_crea_producto_sin_imagen(operador, datos):
    respuesta = operador.post(URL, datos, format="json")
    assert respuesta.status_code == 201
    assert respuesta.data["imagen"] is None


def test_acepta_imagen_jpg(operador, datos):
    imagen = crear_imagen("JPEG", "foto.jpg", "image/jpeg")
    respuesta = operador.post(URL, {**datos, "imagen": imagen}, format="multipart")
    assert respuesta.status_code == 201


def test_nombre_se_guarda_sin_espacios_extra(operador, datos):
    respuesta = operador.post(URL, {**datos, "nombre": "  Doble   carne "}, format="json")
    assert respuesta.data["nombre"] == "Doble carne"


# --- campos obligatorios ---

@pytest.mark.parametrize(
    "campo", ["nombre", "precio_base", "tiempo_preparacion", "categoria", "sedes"]
)
def test_campo_obligatorio(operador, datos, campo):
    datos.pop(campo)
    respuesta = operador.post(URL, datos, format="json")
    assert respuesta.status_code == 400
    assert campo in respuesta.data


def test_nombre_en_blanco(operador, datos):
    respuesta = operador.post(URL, {**datos, "nombre": "   "}, format="json")
    assert respuesta.status_code == 400
    assert "nombre" in respuesta.data


def test_lista_de_sedes_vacia(operador, datos):
    respuesta = operador.post(URL, {**datos, "sedes": []}, format="json")
    assert respuesta.status_code == 400
    assert "Selecciona al menos una sede." in str(respuesta.data["sedes"])


# --- precio y tiempo mayores a 0 ---

@pytest.mark.parametrize("precio", ["0", "-100", "abc"])
def test_precio_invalido(operador, datos, precio):
    respuesta = operador.post(URL, {**datos, "precio_base": precio}, format="json")
    assert respuesta.status_code == 400
    assert "precio_base" in respuesta.data


@pytest.mark.parametrize("tiempo", [0, -5, "diez"])
def test_tiempo_invalido(operador, datos, tiempo):
    respuesta = operador.post(URL, {**datos, "tiempo_preparacion": tiempo}, format="json")
    assert respuesta.status_code == 400
    assert "tiempo_preparacion" in respuesta.data


# --- categoría y sede ---

def test_rechaza_categoria_inactiva(operador, datos):
    inactiva = CategoriaMenu.objects.create(nombre="Viejas", activa=False)
    respuesta = operador.post(URL, {**datos, "categoria": inactiva.id}, format="json")
    assert respuesta.status_code == 400
    assert "inactiva" in str(respuesta.data["categoria"])


def test_rechaza_sede_inactiva(operador, datos):
    cerrada = crear_sede("Sede Cerrada", activa=False)
    respuesta = operador.post(URL, {**datos, "sedes": [cerrada.id]}, format="json")
    assert respuesta.status_code == 400
    assert "sedes" in respuesta.data


# --- imagen inválida o pesada ---

@pytest.mark.parametrize(
    "formato,nombre,tipo",
    [("GIF", "anim.gif", "image/gif"), ("WEBP", "foto.webp", "image/webp")],
)
def test_rechaza_formato_no_permitido(operador, datos, formato, nombre, tipo):
    imagen = crear_imagen(formato, nombre, tipo)
    respuesta = operador.post(URL, {**datos, "imagen": imagen}, format="multipart")
    assert respuesta.status_code == 400
    assert "Formato no permitido" in str(respuesta.data["imagen"])
    assert not Producto.objects.exists()


def test_rechaza_archivo_que_no_es_imagen(operador, datos):
    falso = SimpleUploadedFile("virus.png", b"esto no es una imagen", content_type="image/png")
    respuesta = operador.post(URL, {**datos, "imagen": falso}, format="multipart")
    assert respuesta.status_code == 400
    assert "imagen" in respuesta.data


def test_rechaza_imagen_de_mas_de_2_mb(operador, datos, monkeypatch):
    monkeypatch.setattr(menu_serializers, "TAMANO_MAX_BYTES", 100)
    respuesta = operador.post(URL, {**datos, "imagen": crear_imagen()}, format="multipart")
    assert respuesta.status_code == 400
    assert "no puede superar" in str(respuesta.data["imagen"])


def test_limite_real_es_2_mb():
    assert menu_serializers.TAMANO_MAX_BYTES == 2 * 1024 * 1024


# --- editar ---

def test_editar_precio_se_refleja_para_el_cliente(operador, producto, sede):
    assert menu_cliente(sede)[producto.id]["precio"] == "15000.00"

    respuesta = operador.patch(
        f"{URL}{producto.id}/",
        {"precio_base": "18000", "nombre": "Clásica especial"},
        format="json",
    )

    assert respuesta.status_code == 200, respuesta.data
    visto = menu_cliente(sede)[producto.id]
    assert visto["precio"] == "18000.00"
    assert visto["nombre"] == "Clásica especial"


def test_editar_imagen_reemplaza_el_archivo_y_el_cliente_la_ve(operador, producto, sede):
    url = f"{URL}{producto.id}/"
    operador.patch(url, {"imagen": crear_imagen()}, format="multipart")
    producto.refresh_from_db()
    primera = producto.imagen.name

    operador.patch(url, {"imagen": crear_imagen("JPEG", "b.jpg", "image/jpeg")}, format="multipart")
    producto.refresh_from_db()

    assert producto.imagen.name != primera
    assert not producto.imagen.storage.exists(primera)
    assert menu_cliente(sede)[producto.id]["imagen"].endswith(producto.imagen.name)


def test_editar_con_datos_invalidos_no_cambia_nada(operador, producto):
    respuesta = operador.patch(f"{URL}{producto.id}/", {"precio_base": "0"}, format="json")
    assert respuesta.status_code == 400
    producto.refresh_from_db()
    assert producto.precio_base == Decimal("15000")


def test_quitar_sede_deja_de_ofrecerlo_alli(operador, producto, sede):
    otra = crear_sede("Sede Norte")
    respuesta = operador.patch(f"{URL}{producto.id}/", {"sedes": [otra.id]}, format="json")

    assert respuesta.status_code == 200
    assert respuesta.data["sedes"] == [otra.id]
    assert menu_cliente(sede)[producto.id]["disponible"] is False
    assert menu_cliente(otra)[producto.id]["disponible"] is True


def test_desactivar_producto_lo_oculta_del_menu(operador, producto, sede):
    operador.patch(f"{URL}{producto.id}/", {"activo": False}, format="json")
    assert producto.id not in menu_cliente(sede)


def test_no_se_puede_borrar(operador, producto):
    assert operador.delete(f"{URL}{producto.id}/").status_code == 405


# --- listado ---

def test_lista_y_filtra_por_categoria(operador, producto):
    bebidas = CategoriaMenu.objects.create(nombre="Bebidas")
    Producto.objects.create(
        categoria=bebidas, nombre="Limonada", precio_base=6000, tiempo_preparacion=3,
    )

    todos = operador.get(URL)
    assert todos.status_code == 200
    assert [p["nombre"] for p in todos.data] == ["Limonada", "Clásica"]

    filtrados = operador.get(URL, {"categoria": bebidas.id})
    assert [p["nombre"] for p in filtrados.data] == ["Limonada"]


# --- precio por línea de pedido ---

def test_pedido_viejo_conserva_el_precio_original(operador, producto, sede):
    pedido = Pedido.objects.create(sede=sede, numero_pedido="P-HU11")
    detalle = DetallePedido.objects.create(
        pedido=pedido, producto=producto, cantidad=2,
        precio_unitario=producto.precio_base, subtotal=producto.precio_base * 2,
    )

    operador.patch(f"{URL}{producto.id}/", {"precio_base": "20000"}, format="json")

    detalle.refresh_from_db()
    producto.refresh_from_db()
    assert producto.precio_base == Decimal("20000")
    assert detalle.precio_unitario == Decimal("15000")
    assert detalle.subtotal == Decimal("30000")
