"""Pruebas de HU-25 · El cliente cancela su pedido antes de que entre a preparación."""
from datetime import date, time, timedelta
from decimal import Decimal
from types import SimpleNamespace

import pytest
from django.core import mail
from django.utils import timezone
from rest_framework.exceptions import ValidationError
from rest_framework.test import APIClient

from inventario.models import InventarioInsumo, InventarioProducto
from menu.models import CategoriaMenu, Insumo, Producto, ProductoInsumo
from pedidos.models import ConsumoCupoCombo, EstadoPedido as E, Notificacion, Pedido, TipoNotificacion
from pedidos.servicios import validar_disponibilidad_cupo_sede
from promociones.models import Combo, ComboProducto, ComboSede
from sedes.models import CapacidadSede, Ciudad, Sede, ZonaCobertura
from usuarios.models import Cliente, DireccionEntrega, Usuario

pytestmark = pytest.mark.django_db

CONFIRMAR = "/api/pedidos/confirmar/"
CLAVE = "ClaveSegura2026"


def cancelar(pedido_id):
    return f"/api/pedidos/{pedido_id}/cancelar/"


def crear_cliente(ciudad, email, celular):
    usuario = Usuario.objects.create_user(username=email, email=email, password=CLAVE)
    cliente = Cliente.objects.create(
        usuario=usuario, tipo_documento="CC", num_documento=celular, nombres="Ana",
        apellidos="Prueba", celular=celular, fecha_nacimiento=date(2000, 1, 1),
    )
    direccion = DireccionEntrega.objects.create(
        ciudad=ciudad, cliente=cliente, direccion="Calle 5 # 6-7", latitud=3.46, longitud=-76.53,
    )
    return usuario, direccion


@pytest.fixture
def m():
    ciudad = Ciudad.objects.create(nombre="Cali")
    sede = Sede.objects.create(
        ciudad=ciudad, nombre="Norte", direccion="Calle 1 # 2-3", latitud=3.45,
        longitud=-76.53, barrio="Granada", telefono="3000000000", correo="s@correo.com",
    )
    ZonaCobertura.objects.create(
        sede=sede, nombre="Zona 1", radio=5, centro_latitud=3.45, centro_longitud=-76.53,
        tarifa_domicilio=Decimal("3000"), tiempo_estimado=40, pedido_minimo=Decimal("0"),
    )
    usuario, direccion = crear_cliente(ciudad, "cli@correo.com", "3001234567")
    categoria = CategoriaMenu.objects.create(nombre="Platos")
    producto = Producto.objects.create(
        categoria=categoria, nombre="Hamburguesa", precio_base=Decimal("20000"),
        tiempo_preparacion=15, tipo_control_stock=Producto.TipoControlStock.PRODUCTO,
    )
    inv = InventarioProducto.objects.create(sede=sede, producto=producto, stock_actual=5)
    return SimpleNamespace(
        ciudad=ciudad, sede=sede, usuario=usuario, direccion=direccion,
        categoria=categoria, producto=producto, inv=inv,
    )


@pytest.fixture
def client(m):
    c = APIClient()
    c.force_authenticate(user=m.usuario)
    return c


def confirmar(client, m, items=None):
    items = items or [{"producto_id": m.producto.pk, "cantidad": 2}]
    r = client.post(
        CONFIRMAR,
        {"sede_id": m.sede.pk, "direccion_id": m.direccion.pk, "metodo_pago": "tarjeta", "items": items},
        format="json",
    )
    assert r.status_code == 201, r.data
    pedido = Pedido.objects.latest("pk")
    mail.outbox.clear()
    return pedido


def mover(pedido, estado):
    Pedido.objects.filter(pk=pedido.pk).update(estado=estado)


# --- Criterios 1 y 4: cuándo se puede cancelar y el historial -------------------


@pytest.mark.parametrize("estado", [E.PENDIENTE_APROBACION, E.RECIBIDO])
def test_cancela_en_pendiente_o_recibido_y_queda_en_el_historial(client, m, estado, django_capture_on_commit_callbacks):
    pedido = confirmar(client, m)
    mover(pedido, estado)

    with django_capture_on_commit_callbacks(execute=True):
        r = client.post(cancelar(pedido.pk))

    assert r.status_code == 200
    assert r.data["estado"] == E.CANCELADO
    pedido.refresh_from_db()
    assert pedido.estado == E.CANCELADO
    assert pedido.motivo_cancelacion == "Cancelado por el cliente."
    ultimo = pedido.historial_estados.latest("fecha_hora")
    assert ultimo.estado == E.CANCELADO
    assert ultimo.usuario == m.usuario
    # Sigue apareciendo en su lista de pedidos, como cancelado.
    lista = client.get("/api/pedidos/mios/").data
    assert [(p["id"], p["estado"]) for p in lista] == [(pedido.pk, E.CANCELADO)]


@pytest.mark.parametrize("estado", [E.EN_PREPARACION, E.LISTO_DESPACHO, E.EN_CAMINO])
def test_no_cancela_si_ya_entro_a_preparacion(client, m, estado):
    pedido = confirmar(client, m)
    mover(pedido, estado)

    r = client.post(cancelar(pedido.pk))

    assert r.status_code == 400
    assert r.data["codigo"] == "cancelacion_no_permitida"
    assert "no se puede cancelar" in r.data["detail"]
    pedido.refresh_from_db()
    assert pedido.estado == estado
    m.inv.refresh_from_db()
    assert m.inv.stock_actual == 3  # el stock no se devuelve


def test_no_cancela_un_pedido_ya_cancelado(client, m):
    pedido = confirmar(client, m)
    assert client.post(cancelar(pedido.pk)).status_code == 200

    r = client.post(cancelar(pedido.pk))

    assert r.status_code == 400
    m.inv.refresh_from_db()
    assert m.inv.stock_actual == 5  # no se devuelve dos veces


def test_el_detalle_dice_si_el_cliente_puede_cancelar(client, m):
    pedido = confirmar(client, m)
    assert E.CANCELADO in client.get(f"/api/pedidos/{pedido.pk}/estado/").data["siguientes_estados"]
    mover(pedido, E.EN_PREPARACION)
    assert client.get(f"/api/pedidos/{pedido.pk}/estado/").data["siguientes_estados"] == []


def test_no_cancela_pedidos_ajenos(client, m):
    pedido = confirmar(client, m)
    otro, _ = crear_cliente(m.ciudad, "otro@correo.com", "3009999999")
    ajeno = APIClient()
    ajeno.force_authenticate(user=otro)

    assert ajeno.post(cancelar(pedido.pk)).status_code == 404
    pedido.refresh_from_db()
    assert pedido.estado == E.PENDIENTE_APROBACION


def test_solo_clientes(m):
    personal = Usuario.objects.create_user(username="op@correo.com", email="op@correo.com", password=CLAVE)
    c = APIClient()
    c.force_authenticate(user=personal)
    pedido = Pedido.objects.create(sede=m.sede, numero_pedido="P-1", estado=E.RECIBIDO)
    assert c.post(cancelar(pedido.pk)).status_code == 403
    assert APIClient().post(cancelar(pedido.pk)).status_code == 401


# --- Criterio 3: stock, capacidad y correo ---------------------------------------


def test_devuelve_el_stock_del_producto_y_lo_habilita_si_estaba_agotado(client, m):
    m.inv.stock_actual = 2
    m.inv.save()
    pedido = confirmar(client, m)
    m.inv.refresh_from_db()
    assert (m.inv.stock_actual, m.inv.disponible) == (0, False)

    assert client.post(cancelar(pedido.pk)).status_code == 200

    m.inv.refresh_from_db()
    assert (m.inv.stock_actual, m.inv.disponible) == (2, True)


def test_respeta_lo_que_el_operador_deshabilito_con_stock(client, m):
    pedido = confirmar(client, m)
    InventarioProducto.objects.filter(pk=m.inv.pk).update(disponible=False)

    assert client.post(cancelar(pedido.pk)).status_code == 200

    m.inv.refresh_from_db()
    assert (m.inv.stock_actual, m.inv.disponible) == (5, False)


def test_devuelve_insumos_de_la_receta_sin_los_excluidos(client, m):
    m.producto.tipo_control_stock = Producto.TipoControlStock.INSUMOS
    m.producto.save()
    carne = Insumo.objects.create(nombre="Carne", unidad_medida="kg")
    cebolla = Insumo.objects.create(nombre="Cebolla", unidad_medida="kg")
    ProductoInsumo.objects.create(producto=m.producto, insumo=carne, cantidad_necesaria=Decimal("0.2"))
    ProductoInsumo.objects.create(
        producto=m.producto, insumo=cebolla, cantidad_necesaria=Decimal("0.1"), es_excluible=True
    )
    inv_carne = InventarioInsumo.objects.create(sede=m.sede, insumo=carne, stock_actual=Decimal("1"))
    inv_cebolla = InventarioInsumo.objects.create(sede=m.sede, insumo=cebolla, stock_actual=Decimal("1"))
    pedido = confirmar(client, m, [{"producto_id": m.producto.pk, "cantidad": 2, "exclusiones": [cebolla.pk]}])
    inv_carne.refresh_from_db()
    assert inv_carne.stock_actual == Decimal("0.600")

    assert client.post(cancelar(pedido.pk)).status_code == 200

    inv_carne.refresh_from_db()
    inv_cebolla.refresh_from_db()
    assert inv_carne.stock_actual == Decimal("1.000")
    assert inv_cebolla.stock_actual == Decimal("1.000")


def test_devuelve_el_stock_de_los_productos_del_combo_y_su_cupo(client, m):
    hoy = timezone.localdate()
    combo = Combo.objects.create(
        nombre="Combo pareja", precio=Decimal("35000"),
        fecha_inicio=hoy - timedelta(days=1), fecha_vencimiento=hoy + timedelta(days=1),
    )
    ComboProducto.objects.create(combo=combo, producto=m.producto, cantidad=2)
    ComboSede.objects.create(combo=combo, sede=m.sede, cupo_max_diario=1)
    pedido = confirmar(client, m, [{"combo_id": combo.pk, "cantidad": 1}])
    m.inv.refresh_from_db()
    assert m.inv.stock_actual == 3
    assert ConsumoCupoCombo.objects.filter(pedido=pedido).exists()

    assert client.post(cancelar(pedido.pk)).status_code == 200

    m.inv.refresh_from_db()
    assert m.inv.stock_actual == 5
    # El cupo diario (1) vuelve a estar libre: se puede pedir el combo otra vez.
    confirmar(client, m, [{"combo_id": combo.pk, "cantidad": 1}])


def test_libera_el_cupo_de_capacidad_de_la_sede(client, m):
    CapacidadSede.objects.create(
        sede=m.sede, hora_inicio=time(0, 0), hora_fin=time(23, 59, 59),
        dias_semana="lunes,martes,miercoles,jueves,viernes,sabado,domingo",
        max_pedidos_simultaneos=1, umbral_alerta=1,
    )
    pedido = confirmar(client, m)
    mover(pedido, E.RECIBIDO)
    with pytest.raises(ValidationError):
        validar_disponibilidad_cupo_sede(m.sede)

    assert client.post(cancelar(pedido.pk)).status_code == 200

    assert validar_disponibilidad_cupo_sede(m.sede)[0] is True


def test_envia_correo_y_notificacion(client, m, django_capture_on_commit_callbacks):
    pedido = confirmar(client, m)

    with django_capture_on_commit_callbacks(execute=True):
        client.post(cancelar(pedido.pk))

    assert len(mail.outbox) == 1
    correo = mail.outbox[0]
    assert correo.to == ["cli@correo.com"]
    assert pedido.numero_pedido in correo.subject
    assert "reembolso" in correo.body  # pagó con tarjeta
    assert Notificacion.objects.filter(pedido=pedido, tipo=TipoNotificacion.PEDIDO_CANCELADO).exists()


def test_si_falla_el_correo_la_cancelacion_se_mantiene(client, m, monkeypatch, django_capture_on_commit_callbacks):
    pedido = confirmar(client, m)

    def falla(*args, **kwargs):
        raise ConnectionError("sin servidor de correo")

    monkeypatch.setattr("pedidos.cancelacion.send_mail", falla)
    with django_capture_on_commit_callbacks(execute=True):
        r = client.post(cancelar(pedido.pk))

    assert r.status_code == 200
    pedido.refresh_from_db()
    assert pedido.estado == E.CANCELADO
