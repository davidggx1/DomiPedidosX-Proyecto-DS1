"""Pruebas de HU-69 · Información de clientes para el administrador."""
import json
from decimal import Decimal

import pytest
from django.contrib.auth.models import Group
from rest_framework.test import APIClient

from menu.models import CategoriaMenu, Producto
from pedidos.models import DetallePedido, EstadoPedido as E, Factura, Pedido
from sedes.models import Ciudad, Sede
from usuarios.models import Cliente, DireccionEntrega, Usuario
from usuarios.roles import ADMINISTRADOR, OPERADOR

pytestmark = pytest.mark.django_db

URL = "/api/usuarios/clientes/"
CLAVE = "ClaveSegura2026"


def crear_usuario(email, rol=None):
    usuario = Usuario.objects.create_user(username=email, email=email, password=CLAVE)
    if rol:
        usuario.groups.add(Group.objects.get_or_create(name=rol)[0])
    return usuario


def crear_cliente(email, nombres, apellidos, celular):
    return Cliente.objects.create(
        usuario=crear_usuario(email), tipo_documento="CC", num_documento=celular, nombres=nombres,
        apellidos=apellidos, celular=celular, fecha_nacimiento="2000-01-01",
    )


@pytest.fixture
def admin():
    c = APIClient()
    c.force_authenticate(user=crear_usuario("admin@correo.com", ADMINISTRADOR))
    return c


@pytest.fixture
def ana():
    return crear_cliente("ana@correo.com", "Ana María", "Pérez", "3001112233")


@pytest.fixture
def luis():
    return crear_cliente("luis@otro.com", "Luis", "Gómez", "3159998877")


@pytest.fixture
def sede():
    ciudad = Ciudad.objects.create(nombre="Cali")
    return Sede.objects.create(
        ciudad=ciudad, nombre="Sede Norte", direccion="Calle 1", latitud=3.45, longitud=-76.53,
        barrio="Centro", telefono="3000000000", correo="norte@correo.com",
    )


def crear_pedido(cliente, sede, numero, estado, motivo=""):
    producto = Producto.objects.get_or_create(
        nombre="Hamburguesa",
        defaults={"categoria": CategoriaMenu.objects.get_or_create(nombre="Platos")[0],
                  "precio_base": Decimal("20000"), "tiempo_preparacion": 15},
    )[0]
    pedido = Pedido.objects.create(
        cliente=cliente, sede=sede, numero_pedido=numero, estado=estado, motivo_cancelacion=motivo,
        entrega_direccion="Calle 5 # 6-7",
    )
    DetallePedido.objects.create(
        pedido=pedido, producto=producto, cantidad=2, precio_unitario=Decimal("20000"), subtotal=Decimal("40000")
    )
    Factura.objects.create(
        pedido=pedido, numero=f"F-{numero}", subtotal=Decimal("40000"), iva=Decimal("6387"),
        costo_domicilio=Decimal("3000"), total=Decimal("43000"), metodo_pago="tarjeta",
    )
    return pedido


def ids(respuesta):
    return [c["id"] for c in respuesta.data]


# --- Criterio 1: búsqueda ---------------------------------------------------------


def test_lista_los_clientes_con_contacto_estado_y_fecha_de_registro(admin, ana, luis):
    r = admin.get(URL)

    assert r.status_code == 200
    assert ids(r) == [luis.pk, ana.pk]  # el más reciente primero
    fila = r.data[1]
    assert fila["nombre"] == "Ana María Pérez"
    assert fila["email"] == "ana@correo.com"
    assert fila["celular"] == "3001112233"
    assert fila["activa"] is True
    assert fila["fecha_registro"]
    assert fila["total_pedidos"] == 0


@pytest.mark.parametrize("texto", ["maría", "PÉREZ", "ana pérez", "ana@correo", "1112233"])
def test_busca_por_nombre_correo_o_telefono(admin, ana, luis, texto):
    assert ids(admin.get(URL, {"buscar": texto})) == [ana.pk]


def test_sin_resultados(admin, ana):
    assert ids(admin.get(URL, {"buscar": "zzz"})) == []


def test_muestra_cuentas_desactivadas(admin, ana):
    ana.usuario.is_active = False
    ana.usuario.save()
    assert admin.get(URL).data[0]["activa"] is False


def test_no_incluye_al_personal(admin, ana):
    crear_usuario("op@correo.com", OPERADOR)
    assert ids(admin.get(URL)) == [ana.pk]


# --- Criterio 2: historial de pedidos ---------------------------------------------


def test_la_ficha_trae_el_historial_completo(admin, ana, luis, sede):
    entregado = crear_pedido(ana, sede, "P-1", E.ENTREGADO)
    cancelado = crear_pedido(ana, sede, "P-2", E.CANCELADO, motivo="Cancelado por el cliente.")
    crear_pedido(luis, sede, "P-3", E.RECIBIDO)
    DireccionEntrega.objects.create(
        ciudad=sede.ciudad, cliente=ana, alias="Casa", direccion="Calle 5 # 6-7", latitud=3.4, longitud=-76.5
    )

    r = admin.get(f"{URL}{ana.pk}/")

    assert r.status_code == 200
    assert r.data["total_pedidos"] == 2
    assert [p["id"] for p in r.data["pedidos"]] == [cancelado.pk, entregado.pk]
    pedido = r.data["pedidos"][0]
    assert pedido["estado"] == E.CANCELADO
    assert pedido["motivo_cancelacion"] == "Cancelado por el cliente."
    assert pedido["sede"] == "Sede Norte"
    assert pedido["total"] == "43000.00"
    assert pedido["metodo_pago"] == "Tarjeta"
    assert pedido["resumen"] == ["2x Hamburguesa"]
    assert [d["alias"] for d in r.data["direcciones"]] == ["Casa"]


def test_ficha_inexistente(admin):
    assert admin.get(f"{URL}999/").status_code == 404


# --- Criterio 3: sin datos de autenticación ---------------------------------------


def test_no_expone_contrasena_ni_datos_de_autenticacion(admin, ana, sede):
    crear_pedido(ana, sede, "P-1", E.ENTREGADO)
    lista = json.dumps(admin.get(URL).data, default=str)
    ficha = json.dumps(admin.get(f"{URL}{ana.pk}/").data, default=str)

    for texto in (lista, ficha):
        assert ana.usuario.password not in texto
        for clave in ('"password"', "pbkdf2", '"last_login"', '"is_superuser"', '"groups"', "user_permissions"):
            assert clave not in texto


# --- Permisos ---------------------------------------------------------------------


def test_solo_el_administrador(ana):
    operador = APIClient()
    operador.force_authenticate(user=crear_usuario("op@correo.com", OPERADOR))
    cliente = APIClient()
    cliente.force_authenticate(user=ana.usuario)

    for c in (operador, cliente):
        assert c.get(URL).status_code == 403
        assert c.get(f"{URL}{ana.pk}/").status_code == 403
    assert APIClient().get(URL).status_code == 401
