"""HU-33 · Cocina cancela un pedido por error de cocina, con justificación obligatoria."""
from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from unittest import mock

import pytest
from django.contrib.auth.models import Group
from django.core import mail
from rest_framework.test import APIClient

from inventario.models import InventarioProducto
from menu.models import CategoriaMenu, Producto
from pedidos import cancelacion
from pedidos.capacidad import pedidos_que_ocupan_cupo
from pedidos.models import EstadoPedido as E, Notificacion, Pedido, TipoNotificacion
from sedes.models import Ciudad, Sede, ZonaCobertura
from usuarios.models import Cliente, DireccionEntrega, Empleado, Usuario

pytestmark = pytest.mark.django_db

CLAVE = "ClaveSegura2026"


def url(pedido):
    return f"/api/pedidos/{pedido.pk}/cancelar-cocina/"


def crear_sede(ciudad, nombre):
    sede = Sede.objects.create(
        ciudad=ciudad, nombre=nombre, direccion="Calle 1 # 2-3", latitud=3.45, longitud=-76.53,
        barrio="Granada", telefono="3000000000", correo=f"{nombre.lower()}@correo.com",
    )
    ZonaCobertura.objects.create(
        sede=sede, nombre=f"Zona {nombre}", radio=5, centro_latitud=3.45, centro_longitud=-76.53,
        tarifa_domicilio=Decimal("3000"), tiempo_estimado=40, pedido_minimo=Decimal("0"),
    )
    return sede


def crear_personal(email, rol, sede, documento):
    usuario = Usuario.objects.create_user(username=email, email=email, password=CLAVE)
    usuario.groups.add(Group.objects.get_or_create(name=rol)[0])
    Empleado.objects.create(
        usuario=usuario, sede=sede, tipo_documento="CC", num_documento=documento,
        nombres="Carla", apellidos="Gómez", celular="3000000000", direccion="Calle 1",
    )
    return usuario


def api_de(usuario):
    api = APIClient()
    api.force_authenticate(user=usuario)
    return api


@pytest.fixture
def m():
    ciudad = Ciudad.objects.create(nombre="Cali")
    sede = crear_sede(ciudad, "Norte")
    usuario = Usuario.objects.create_user(username="cli@correo.com", email="cli@correo.com", password=CLAVE)
    cliente = Cliente.objects.create(
        usuario=usuario, tipo_documento="CC", num_documento="3001234567", nombres="Ana",
        apellidos="Prueba", celular="3001234567", fecha_nacimiento=date(2000, 1, 1),
    )
    direccion = DireccionEntrega.objects.create(
        ciudad=ciudad, cliente=cliente, direccion="Calle 5 # 6-7", latitud=3.46, longitud=-76.53,
    )
    categoria = CategoriaMenu.objects.create(nombre="Platos")
    producto = Producto.objects.create(
        categoria=categoria, nombre="Hamburguesa", precio_base=Decimal("20000"),
        tiempo_preparacion=15, tipo_control_stock=Producto.TipoControlStock.PRODUCTO,
    )
    inv = InventarioProducto.objects.create(sede=sede, producto=producto, stock_actual=5)
    cocinero = crear_personal("cocina@correo.com", "cocina", sede, "201")
    return SimpleNamespace(
        ciudad=ciudad, sede=sede, usuario=usuario, direccion=direccion, producto=producto,
        inv=inv, cocinero=cocinero, cocina=api_de(cocinero),
    )


@pytest.fixture
def avisos():
    """Captura los eventos enviados al operador (sin channel layer real)."""
    with mock.patch.object(cancelacion, "async_to_sync") as envio:
        yield envio


def crear_pedido(m, estado=E.RECIBIDO, cantidad=2):
    cliente = APIClient()
    cliente.force_authenticate(user=m.usuario)
    r = cliente.post(
        "/api/pedidos/confirmar/",
        {
            "sede_id": m.sede.pk, "direccion_id": m.direccion.pk, "metodo_pago": "tarjeta",
            "items": [{"producto_id": m.producto.pk, "cantidad": cantidad}],
        },
        format="json",
    )
    assert r.status_code == 201, r.data
    pedido = Pedido.objects.latest("pk")
    Pedido.objects.filter(pk=pedido.pk).update(estado=estado)
    mail.outbox.clear()
    return pedido


# --- Criterio 1: justificación obligatoria ----------------------------------------


@pytest.mark.parametrize("justificacion", [None, "", "   ", "abc"])
def test_exige_una_justificacion(m, justificacion, avisos):
    pedido = crear_pedido(m)
    datos = {} if justificacion is None else {"justificacion": justificacion}

    r = m.cocina.post(url(pedido), datos, format="json")

    assert r.status_code == 400
    assert r.data["codigo"] == "motivo_obligatorio"
    assert "justificacion" in r.data
    pedido.refresh_from_db()
    assert pedido.estado == E.RECIBIDO


def test_rechaza_justificacion_demasiado_larga(m, avisos):
    pedido = crear_pedido(m)
    r = m.cocina.post(url(pedido), {"justificacion": "x" * 501}, format="json")
    assert r.status_code == 400
    assert r.data["codigo"] == "motivo_muy_largo"


# --- Criterio 2: estado, motivo, inventario y capacidad --------------------------


@pytest.mark.parametrize("estado", [E.RECIBIDO, E.EN_PREPARACION])
def test_cancela_con_motivo_de_error_de_cocina(m, estado, avisos, django_capture_on_commit_callbacks):
    pedido = crear_pedido(m, estado)

    with django_capture_on_commit_callbacks(execute=True):
        r = m.cocina.post(url(pedido), {"justificacion": "  Se quemó   la carne "}, format="json")

    assert r.status_code == 200
    assert r.data["estado"] == E.CANCELADO
    pedido.refresh_from_db()
    assert pedido.estado == E.CANCELADO
    assert pedido.motivo_cancelacion == "Cancelado por error de cocina: Se quemó la carne"
    ultimo = pedido.historial_estados.latest("fecha_hora")
    assert (ultimo.estado, ultimo.usuario, ultimo.observacion) == (
        E.CANCELADO, m.cocinero, "Cancelado por error de cocina: Se quemó la carne",
    )


def test_devuelve_el_stock_y_libera_la_capacidad(m, avisos):
    pedido = crear_pedido(m, cantidad=2)
    m.inv.refresh_from_db()
    assert m.inv.stock_actual == 3
    assert pedidos_que_ocupan_cupo(m.sede) == 1

    m.cocina.post(url(pedido), {"justificacion": "Se dañó el pan"}, format="json")

    m.inv.refresh_from_db()
    assert m.inv.stock_actual == 5
    assert pedidos_que_ocupan_cupo(m.sede) == 0


@pytest.mark.parametrize("estado", [E.PENDIENTE_APROBACION, E.LISTO_DESPACHO, E.EN_CAMINO, E.ENTREGADO])
def test_no_cancela_fuera_de_cocina(m, estado, avisos):
    pedido = crear_pedido(m, estado)

    r = m.cocina.post(url(pedido), {"justificacion": "Se dañó el pan"}, format="json")

    assert r.status_code == 400
    pedido.refresh_from_db()
    assert pedido.estado == estado
    m.inv.refresh_from_db()
    assert m.inv.stock_actual == 3


def test_no_cancela_dos_veces_ni_devuelve_el_stock_dos_veces(m, avisos):
    pedido = crear_pedido(m)
    assert m.cocina.post(url(pedido), {"justificacion": "Se dañó el pan"}, format="json").status_code == 200

    r = m.cocina.post(url(pedido), {"justificacion": "Se dañó el pan"}, format="json")

    assert r.status_code == 400
    assert r.data["codigo"] == "pedido_cerrado"
    m.inv.refresh_from_db()
    assert m.inv.stock_actual == 5


# --- Criterio 3: avisos al cliente y al operador ----------------------------------


def test_avisa_al_cliente_por_notificacion_y_correo(m, avisos, django_capture_on_commit_callbacks):
    pedido = crear_pedido(m)

    with django_capture_on_commit_callbacks(execute=True):
        m.cocina.post(url(pedido), {"justificacion": "Se dañó el pan"}, format="json")

    notificacion = Notificacion.objects.get(usuario=m.usuario, tipo=TipoNotificacion.PEDIDO_CANCELADO)
    assert "error de cocina" in notificacion.mensaje
    assert "Se dañó el pan" in notificacion.mensaje
    # Un solo correo al cliente: el de cambio de estado de HU-50, con el motivo
    correos = [c for c in mail.outbox if c.to == ["cli@correo.com"]]
    assert len(correos) == 1
    assert pedido.numero_pedido in correos[0].subject
    assert "Motivo: Cancelado por error de cocina: Se dañó el pan" in correos[0].body


def test_avisa_en_la_pantalla_del_operador(m, avisos, django_capture_on_commit_callbacks):
    pedido = crear_pedido(m)

    with django_capture_on_commit_callbacks(execute=True):
        m.cocina.post(url(pedido), {"justificacion": "Se dañó el pan"}, format="json")

    grupo, evento = avisos.return_value.call_args.args
    assert grupo == f"pedidos_sede_{m.sede.pk}"
    datos = evento["data"]
    assert datos["tipo"] == "pedido_cancelado_cocina"
    assert datos["pedido"] == {"id": pedido.pk, "numero_pedido": pedido.numero_pedido, "estado": E.CANCELADO}
    assert datos["justificacion"] == "Se dañó el pan"
    assert datos["usuario_nombre"] == "Carla Gómez"
    assert datos["fecha_hora"]


def test_si_falla_el_canal_la_cancelacion_se_mantiene(m, avisos, django_capture_on_commit_callbacks):
    avisos.side_effect = RuntimeError("sin canal")
    pedido = crear_pedido(m)

    with django_capture_on_commit_callbacks(execute=True):
        r = m.cocina.post(url(pedido), {"justificacion": "Se dañó el pan"}, format="json")

    assert r.status_code == 200
    pedido.refresh_from_db()
    assert pedido.estado == E.CANCELADO


# --- La ruta genérica de estado también devuelve el stock ------------------------


def test_cancelar_por_patch_de_estado_usa_la_misma_regla(m, avisos):
    pedido = crear_pedido(m)

    sin_motivo = m.cocina.patch(f"/api/pedidos/{pedido.pk}/estado/", {"estado": E.CANCELADO}, format="json")
    assert sin_motivo.status_code == 400
    assert "motivo" in sin_motivo.data

    r = m.cocina.patch(
        f"/api/pedidos/{pedido.pk}/estado/", {"estado": E.CANCELADO, "motivo": "Se dañó el pan"}, format="json"
    )
    assert r.status_code == 200
    pedido.refresh_from_db()
    assert pedido.motivo_cancelacion == "Cancelado por error de cocina: Se dañó el pan"
    m.inv.refresh_from_db()
    assert m.inv.stock_actual == 5


# --- Permisos ----------------------------------------------------------------------


def test_cocina_de_otra_sede_no_ve_el_pedido(m, avisos):
    pedido = crear_pedido(m)
    otra = crear_personal("cocina.sur@correo.com", "cocina", crear_sede(m.ciudad, "Sur"), "202")

    r = api_de(otra).post(url(pedido), {"justificacion": "Se dañó el pan"}, format="json")

    assert r.status_code == 404


@pytest.mark.parametrize("rol", ["operador", "repartidor"])
def test_otros_roles_no_usan_este_endpoint(m, rol, avisos):
    pedido = crear_pedido(m)
    otro = crear_personal(f"{rol}@correo.com", rol, m.sede, "301")
    assert api_de(otro).post(url(pedido), {"justificacion": "Se dañó el pan"}, format="json").status_code == 403


def test_el_cliente_no_usa_este_endpoint(m, avisos):
    pedido = crear_pedido(m)
    cliente = api_de(m.usuario)
    assert cliente.post(url(pedido), {"justificacion": "Se dañó el pan"}, format="json").status_code == 403
