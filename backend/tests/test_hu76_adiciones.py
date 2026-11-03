"""Pruebas de HU-76 · Adiciones de un producto (SCRUM-33)."""
from decimal import Decimal

import pytest
from django.contrib.auth.models import Group
from rest_framework.test import APIClient

from menu.models import Adicion, CategoriaMenu, Insumo, Producto, ProductoAdicion
from pedidos.models import DetallePedido, DetallePedidoAdicion, Pedido
from sedes.models import Ciudad, Sede
from usuarios.models import Usuario

pytestmark = pytest.mark.django_db

URL = "/api/menu/adiciones/"
CLAVE = "ClaveSegura#2026"


def crear_usuario(email, rol=None, **extra):
    usuario = Usuario.objects.create_user(username=email, email=email, password=CLAVE, **extra)
    if rol:
        usuario.groups.add(Group.objects.get_or_create(name=rol)[0])
    return usuario


def cliente_api(usuario=None):
    api = APIClient()
    if usuario:
        api.force_authenticate(usuario)
    return api


@pytest.fixture
def api_operador():
    return cliente_api(crear_usuario("operador@correo.com", "operador"))


@pytest.fixture
def queso():
    return Insumo.objects.create(nombre="Queso", unidad_medida="g")


@pytest.fixture
def adicion(queso):
    return Adicion.objects.create(nombre="Queso extra", precio=Decimal("3000"), insumo=queso)


@pytest.fixture
def producto():
    categoria = CategoriaMenu.objects.create(nombre="Hamburguesas")
    return Producto.objects.create(
        categoria=categoria, nombre="Clásica", precio_base=15000, tiempo_preparacion=15
    )


def datos_validos(insumo, **cambios):
    return {"nombre": "Queso extra", "precio": "3000", "insumo": insumo.id, **cambios}


# --- Criterio 1: crear adiciones con nombre y costo extra ---------------------


def test_operador_crea_adicion(api_operador, queso):
    respuesta = api_operador.post(URL, datos_validos(queso), format="json")

    assert respuesta.status_code == 201
    assert respuesta.data["nombre"] == "Queso extra"
    assert Decimal(respuesta.data["precio"]) == Decimal("3000")
    assert respuesta.data["activa"] is True
    assert Adicion.objects.filter(nombre="Queso extra").exists()


def test_precio_cero_es_valido(api_operador, queso):
    respuesta = api_operador.post(URL, datos_validos(queso, precio="0"), format="json")
    assert respuesta.status_code == 201


# --- Criterio 3: nombre obligatorio y precio no negativo ----------------------


@pytest.mark.parametrize("nombre", ["", "   "])
def test_nombre_vacio_es_rechazado(api_operador, queso, nombre):
    respuesta = api_operador.post(URL, datos_validos(queso, nombre=nombre), format="json")

    assert respuesta.status_code == 400
    assert "nombre" in respuesta.data
    assert not Adicion.objects.exists()


def test_precio_negativo_es_rechazado(api_operador, queso):
    respuesta = api_operador.post(URL, datos_validos(queso, precio="-500"), format="json")

    assert respuesta.status_code == 400
    assert "precio" in respuesta.data
    assert not Adicion.objects.exists()


def test_nombre_repetido_es_rechazado(api_operador, adicion, queso):
    respuesta = api_operador.post(URL, datos_validos(queso, nombre="QUESO EXTRA"), format="json")

    assert respuesta.status_code == 400
    assert "nombre" in respuesta.data


def test_insumo_inactivo_es_rechazado(api_operador):
    inactivo = Insumo.objects.create(nombre="Salsa vieja", unidad_medida="ml", activo=False)
    respuesta = api_operador.post(URL, datos_validos(inactivo), format="json")

    assert respuesta.status_code == 400
    assert "insumo" in respuesta.data


# --- Editar y eliminar ---------------------------------------------------------


def test_operador_edita_precio(api_operador, adicion):
    respuesta = api_operador.patch(f"{URL}{adicion.id}/", {"precio": "3500"}, format="json")

    assert respuesta.status_code == 200
    adicion.refresh_from_db()
    assert adicion.precio == Decimal("3500")


def test_eliminar_es_borrado_logico(api_operador, adicion):
    respuesta = api_operador.delete(f"{URL}{adicion.id}/")

    assert respuesta.status_code == 204
    adicion.refresh_from_db()
    assert adicion.activa is False

    activas = api_operador.get(URL, {"activa": "true"})
    assert adicion.id not in [a["id"] for a in activas.data]


def test_adicion_eliminada_se_puede_restaurar(api_operador, adicion):
    api_operador.delete(f"{URL}{adicion.id}/")
    respuesta = api_operador.patch(f"{URL}{adicion.id}/", {"activa": True}, format="json")

    assert respuesta.status_code == 200
    adicion.refresh_from_db()
    assert adicion.activa is True


# --- Criterio 4: editar o eliminar no cambia el historial de pedidos -----------


def test_editar_y_eliminar_no_cambia_pedidos_anteriores(api_operador, adicion, producto):
    ciudad = Ciudad.objects.create(nombre="Cali")
    sede = Sede.objects.create(
        ciudad=ciudad, nombre="Sede Centro", direccion="Cra 1 # 2-3", latitud=3.45,
        longitud=-76.53, barrio="Centro", telefono="3000000000", correo="centro@domi.com",
    )
    pedido = Pedido.objects.create(sede=sede, numero_pedido="P-100")
    detalle = DetallePedido.objects.create(
        pedido=pedido, producto=producto, cantidad=1, precio_unitario=15000, subtotal=18000
    )
    en_pedido = DetallePedidoAdicion.objects.create(
        detalle_pedido=detalle, adicion=adicion, cantidad=1, precio_unitario=Decimal("3000")
    )

    api_operador.patch(f"{URL}{adicion.id}/", {"precio": "5000"}, format="json")
    api_operador.delete(f"{URL}{adicion.id}/")

    en_pedido.refresh_from_db()
    assert en_pedido.precio_unitario == Decimal("3000")
    assert en_pedido.adicion_id == adicion.id


# --- Adiciones por producto ------------------------------------------------------


def url_producto(producto):
    return f"/api/menu/productos/{producto.id}/adiciones/"


def test_asignar_adicion_a_producto(api_operador, adicion, producto):
    respuesta = api_operador.post(
        url_producto(producto), {"adicion": adicion.id, "max_cantidad": 2}, format="json"
    )

    assert respuesta.status_code == 201
    assert respuesta.data["adicion_nombre"] == "Queso extra"
    assert ProductoAdicion.objects.filter(producto=producto, adicion=adicion).exists()

    lista = api_operador.get(url_producto(producto))
    assert [item["adicion"] for item in lista.data] == [adicion.id]


def test_no_se_asigna_dos_veces_la_misma_adicion(api_operador, adicion, producto):
    api_operador.post(url_producto(producto), {"adicion": adicion.id}, format="json")
    respuesta = api_operador.post(url_producto(producto), {"adicion": adicion.id}, format="json")

    assert respuesta.status_code == 400
    assert "adicion" in respuesta.data


def test_no_se_asigna_una_adicion_eliminada(api_operador, adicion, producto):
    adicion.activa = False
    adicion.save()
    respuesta = api_operador.post(url_producto(producto), {"adicion": adicion.id}, format="json")

    assert respuesta.status_code == 400


def test_max_cantidad_debe_ser_al_menos_uno(api_operador, adicion, producto):
    respuesta = api_operador.post(
        url_producto(producto), {"adicion": adicion.id, "max_cantidad": 0}, format="json"
    )

    assert respuesta.status_code == 400
    assert "max_cantidad" in respuesta.data


def test_quitar_adicion_del_producto_no_borra_la_adicion(api_operador, adicion, producto):
    vinculo = ProductoAdicion.objects.create(producto=producto, adicion=adicion)
    respuesta = api_operador.delete(f"{url_producto(producto)}{vinculo.id}/")

    assert respuesta.status_code == 204
    assert not ProductoAdicion.objects.filter(pk=vinculo.pk).exists()
    assert Adicion.objects.filter(pk=adicion.pk, activa=True).exists()


def test_producto_inexistente_responde_404(api_operador):
    assert api_operador.get("/api/menu/productos/9999/adiciones/").status_code == 404


# --- Permisos ----------------------------------------------------------------------


def test_sin_sesion_responde_401():
    assert cliente_api().get(URL).status_code == 401


def test_cliente_no_puede_gestionar_adiciones(queso):
    api = cliente_api(crear_usuario("cliente@correo.com", "cliente"))

    assert api.get(URL).status_code == 403
    assert api.post(URL, datos_validos(queso), format="json").status_code == 403


def test_administrador_puede_gestionar_adiciones():
    api = cliente_api(crear_usuario("admin@correo.com", "administrador"))
    assert api.get(URL).status_code == 200


def test_superusuario_puede_gestionar_adiciones():
    admin = Usuario.objects.create_superuser(username="root", email="root@correo.com", password=CLAVE)
    assert cliente_api(admin).get(URL).status_code == 200
