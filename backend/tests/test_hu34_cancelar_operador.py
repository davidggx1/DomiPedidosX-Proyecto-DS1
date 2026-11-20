"""HU-34 · El operador cancela un pedido no entregado indicando el motivo."""
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
from pedidos import signals
from pedidos.capacidad import pedidos_que_ocupan_cupo
from pedidos.models import EstadoPedido as E, Notificacion, Pedido, TipoNotificacion
from promociones import cupos
from promociones.models import Promocion
from sedes.models import Ciudad, Sede, ZonaCobertura
from usuarios.models import Cliente, DireccionEntrega, Empleado, Repartidor, Usuario

pytestmark = pytest.mark.django_db

CLAVE = "ClaveSegura2026"
EN_CURSO = "/api/pedidos/en-curso/"
NO_FINALES = [
    E.PENDIENTE_APROBACION, E.RECIBIDO, E.EN_PREPARACION, E.LISTO_DESPACHO, E.RECOGIDO, E.EN_CAMINO,
]


def url(pedido):
    return f"/api/pedidos/{pedido.pk}/cancelar-operador/"


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
    otra_sede = crear_sede(ciudad, "Sur")
    usuario = Usuario.objects.create_user(username="cli@correo.com", email="cli@correo.com", password=CLAVE)
    cliente = Cliente.objects.create(
        usuario=usuario, tipo_documento="CC", num_documento="3001234567", nombres="Ana",
        apellidos="Prueba", celular="3001234567", fecha_nacimiento=date(2000, 1, 1),
    )
    direccion = DireccionEntrega.objects.create(
        ciudad=ciudad, cliente=cliente, direccion="Calle 5 # 6-7", latitud=3.46, longitud=-76.53,
    )
    producto = Producto.objects.create(
        categoria=CategoriaMenu.objects.create(nombre="Platos"), nombre="Hamburguesa",
        precio_base=Decimal("20000"), tiempo_preparacion=15,
        tipo_control_stock=Producto.TipoControlStock.PRODUCTO,
    )
    inv = InventarioProducto.objects.create(sede=sede, producto=producto, stock_actual=5)
    operador = crear_personal("op@correo.com", "operador", sede, "101")
    domiciliario = crear_personal("rep@correo.com", "repartidor", sede, "301")
    repartidor = Repartidor.objects.create(empleado=domiciliario.empleado, disponible=True)
    admin = crear_personal("admin@correo.com", "administrador", None, "401")
    return SimpleNamespace(
        sede=sede, otra_sede=otra_sede, usuario=usuario, direccion=direccion, producto=producto,
        inv=inv, operador=operador, api=api_de(operador), repartidor=repartidor, admin=admin,
    )


def crear_pedido(m, estado=E.RECIBIDO, cantidad=2, **extra):
    cliente = APIClient()
    cliente.force_authenticate(user=m.usuario)
    r = cliente.post(
        "/api/pedidos/confirmar/",
        {
            "sede_id": m.sede.pk, "direccion_id": m.direccion.pk, "metodo_pago": "tarjeta",
            "items": [{"producto_id": m.producto.pk, "cantidad": cantidad}], **extra,
        },
        format="json",
    )
    assert r.status_code == 201, r.data
    pedido = Pedido.objects.latest("pk")
    Pedido.objects.filter(pk=pedido.pk).update(estado=estado)
    mail.outbox.clear()
    return pedido


# --- Criterio 1: cualquier pedido no entregado, con motivo obligatorio -----------


@pytest.mark.parametrize("estado", NO_FINALES)
def test_cancela_en_cualquier_estado_no_final(m, estado):
    pedido = crear_pedido(m, estado)

    r = m.api.post(url(pedido), {"motivo": "  Cliente lo  solicitó: ya no lo quiere "}, format="json")

    assert r.status_code == 200, r.data
    assert r.data["estado"] == E.CANCELADO
    pedido.refresh_from_db()
    assert pedido.motivo_cancelacion == "Cliente lo solicitó: ya no lo quiere"


@pytest.mark.parametrize("motivo", [None, "", "   ", "abc"])
def test_exige_el_motivo(m, motivo):
    pedido = crear_pedido(m)
    datos = {} if motivo is None else {"motivo": motivo}

    r = m.api.post(url(pedido), datos, format="json")

    assert r.status_code == 400
    assert r.data["codigo"] == "motivo_obligatorio"
    assert "motivo" in r.data
    pedido.refresh_from_db()
    assert pedido.estado == E.RECIBIDO


def test_rechaza_un_motivo_demasiado_largo(m):
    r = m.api.post(url(crear_pedido(m)), {"motivo": "x" * 501}, format="json")
    assert r.status_code == 400
    assert r.data["codigo"] == "motivo_muy_largo"


# --- Criterio 2: ni entregados ni ya cancelados ---------------------------------


@pytest.mark.parametrize("estado", [E.ENTREGADO, E.CANCELADO])
def test_no_cancela_pedidos_cerrados(m, estado):
    pedido = crear_pedido(m, estado)

    r = m.api.post(url(pedido), {"motivo": "Incidente en la sede"}, format="json")

    assert r.status_code == 400
    assert r.data["codigo"] == "pedido_cerrado"
    m.inv.refresh_from_db()
    assert m.inv.stock_actual == 3


def test_no_devuelve_el_stock_dos_veces(m):
    pedido = crear_pedido(m)
    assert m.api.post(url(pedido), {"motivo": "Incidente en la sede"}, format="json").status_code == 200
    assert m.api.post(url(pedido), {"motivo": "Incidente en la sede"}, format="json").status_code == 400
    m.inv.refresh_from_db()
    assert m.inv.stock_actual == 5


# --- Criterio 3: stock, cocina, cupo de promoción y domiciliario ----------------


def test_devuelve_el_stock_y_libera_la_cocina(m):
    pedido = crear_pedido(m, E.EN_PREPARACION, cantidad=2)
    m.inv.refresh_from_db()
    assert m.inv.stock_actual == 3
    assert pedidos_que_ocupan_cupo(m.sede) == 1

    m.api.post(url(pedido), {"motivo": "Incidente en la sede"}, format="json")

    m.inv.refresh_from_db()
    assert m.inv.stock_actual == 5
    assert pedidos_que_ocupan_cupo(m.sede) == 0


def test_devuelve_el_cupo_de_la_promocion(m):
    hoy = date.today()
    promo = Promocion.objects.create(
        sede=m.sede, nombre="PROMO10", tipo_descuento="porcentaje", valor=10,
        fecha_inicio=hoy, fecha_fin=hoy, cupo_max_diario=1,
    )
    pedido = crear_pedido(m, codigo_promocion="PROMO10")
    assert cupos.cupo_restante(promo) == 0

    m.api.post(url(pedido), {"motivo": "Cliente lo solicitó"}, format="json")

    assert cupos.cupo_restante(promo) == 1


@pytest.mark.parametrize("estado", [E.LISTO_DESPACHO, E.RECOGIDO, E.EN_CAMINO])
def test_desasigna_al_domiciliario_y_le_avisa(m, estado, django_capture_on_commit_callbacks):
    pedido = crear_pedido(m, estado)
    Pedido.objects.filter(pk=pedido.pk).update(repartidor=m.repartidor, asignacion_automatica=True)

    with mock.patch.object(signals, "avisar_repartidor") as aviso:
        with django_capture_on_commit_callbacks(execute=True):
            r = m.api.post(url(pedido), {"motivo": "Dirección errada"}, format="json")

    assert r.status_code == 200
    pedido.refresh_from_db()
    assert pedido.repartidor_id is None
    assert pedido.asignacion_automatica is False
    repartidor_id, pedido_id, datos = aviso.call_args.args
    assert (repartidor_id, pedido_id, datos["motivo"]) == (m.repartidor.pk, pedido.pk, "cancelado")


# --- Criterio 4: auditoría y avisos ----------------------------------------------


def test_audita_usuario_motivo_y_fecha(m):
    pedido = crear_pedido(m, E.EN_CAMINO)
    Pedido.objects.filter(pk=pedido.pk).update(repartidor=m.repartidor)

    m.api.post(url(pedido), {"motivo": "Incidente en la sede"}, format="json")

    ultimo = pedido.historial_estados.latest("fecha_hora")
    assert ultimo.estado == E.CANCELADO
    assert ultimo.usuario == m.operador
    assert ultimo.fecha_hora is not None
    assert ultimo.observacion == "Incidente en la sede (domiciliario asignado: Carla Gómez)"


def test_avisa_al_cliente_por_notificacion_y_correo(m, django_capture_on_commit_callbacks):
    pedido = crear_pedido(m)

    with django_capture_on_commit_callbacks(execute=True):
        m.api.post(url(pedido), {"motivo": "Producto agotado"}, format="json")

    notificacion = Notificacion.objects.get(usuario=m.usuario, tipo=TipoNotificacion.PEDIDO_CANCELADO)
    assert notificacion.mensaje.endswith("fue cancelado por la sede: Producto agotado")
    assert any("Producto agotado" in correo.body for correo in mail.outbox)


def test_cambiar_estado_a_cancelado_tambien_revierte(m):
    """PATCH /estado/ del operador pasa por el mismo servicio: devuelve el stock."""
    pedido = crear_pedido(m)

    r = m.api.patch(
        f"/api/pedidos/{pedido.pk}/estado/", {"estado": "cancelado", "motivo": "Cliente lo solicitó"},
        format="json",
    )

    assert r.status_code == 200, r.data
    m.inv.refresh_from_db()
    assert m.inv.stock_actual == 5


# --- Permisos y alcance por sede --------------------------------------------------


def test_un_pedido_de_otra_sede_responde_404(m):
    pedido = crear_pedido(m)
    otro = api_de(crear_personal("op2@correo.com", "operador", m.otra_sede, "102"))

    assert otro.post(url(pedido), {"motivo": "Incidente en la sede"}, format="json").status_code == 404


@pytest.mark.parametrize("rol", ["cocina", "repartidor"])
def test_otros_roles_no_pueden(m, rol):
    pedido = crear_pedido(m)
    api = api_de(crear_personal(f"{rol}2@correo.com", rol, m.sede, "999"))

    assert api.post(url(pedido), {"motivo": "Incidente en la sede"}, format="json").status_code == 403


def test_el_cliente_no_puede(m):
    pedido = crear_pedido(m)
    assert api_de(m.usuario).post(url(pedido), {"motivo": "Ya no lo quiero"}, format="json").status_code == 403


def test_el_administrador_puede_cancelar_en_cualquier_sede(m):
    pedido = crear_pedido(m, E.EN_PREPARACION)
    r = api_de(m.admin).post(url(pedido), {"motivo": "Incidente en la sede"}, format="json")
    assert r.status_code == 200


# --- Lista "Pedidos en curso" -----------------------------------------------------


def test_en_curso_lista_solo_los_no_finales_de_la_sede(m):
    InventarioProducto.objects.filter(pk=m.inv.pk).update(stock_actual=10)
    activo = crear_pedido(m, E.EN_CAMINO)
    Pedido.objects.filter(pk=activo.pk).update(repartidor=m.repartidor)
    crear_pedido(m, E.ENTREGADO)
    crear_pedido(m, E.CANCELADO)
    Pedido.objects.create(numero_pedido="OTRA-1", sede=m.otra_sede, estado=E.RECIBIDO)

    r = m.api.get(EN_CURSO)

    assert r.status_code == 200
    assert [p["id"] for p in r.data] == [activo.pk]
    fila = r.data[0]
    assert fila["estado_display"] == "En camino"
    assert fila["cliente"] == "Ana Prueba"
    assert fila["resumen"] == ["2x Hamburguesa"]
    assert fila["repartidor"]["nombre"] == "Carla Gómez"


def test_en_curso_no_es_para_cocina(m):
    api = api_de(crear_personal("co@correo.com", "cocina", m.sede, "201"))
    assert api.get(EN_CURSO).status_code == 403
