"""HU-50: correos de estado del pedido (confirmación, cambios de estado y cancelación)."""
import logging
from datetime import date, time
from decimal import Decimal
from types import SimpleNamespace

import pytest
from django.core import mail
from rest_framework.test import APIClient

from inventario.models import InventarioProducto
from menu.models import CategoriaMenu, Producto
from pedidos.estados import cambiar_estado
from pedidos.models import EstadoPedido as E, Pedido
from sedes.models import CapacidadSede, Ciudad, Sede, ZonaCobertura
from usuarios.models import Cliente, DireccionEntrega, Usuario

pytestmark = pytest.mark.django_db


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
    usuario = Usuario.objects.create_user(username="cli@correo.com", email="cli@correo.com", password="ClaveSegura2026")
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
    InventarioProducto.objects.create(sede=sede, producto=producto, stock_actual=10)
    CapacidadSede.objects.create(
        sede=sede, hora_inicio=time(0, 0), hora_fin=time(23, 59, 59),
        dias_semana="lunes,martes,miercoles,jueves,viernes,sabado,domingo",
        max_pedidos_simultaneos=10, umbral_alerta=8,
    )
    return SimpleNamespace(sede=sede, usuario=usuario, cliente=cliente, direccion=direccion, producto=producto)


@pytest.fixture
def pedido(m, django_capture_on_commit_callbacks):
    """Pedido confirmado por el cliente por la API (queda pendiente de aprobación)."""
    api = APIClient()
    api.force_authenticate(m.usuario)
    with django_capture_on_commit_callbacks(execute=True):
        respuesta = api.post(
            "/api/pedidos/confirmar/",
            {
                "sede_id": m.sede.pk, "direccion_id": m.direccion.pk, "metodo_pago": "efectivo",
                "items": [{"producto_id": m.producto.pk, "cantidad": 2}],
            },
            format="json",
        )
    assert respuesta.status_code == 201, respuesta.data
    return Pedido.objects.latest("pk")


def avanzar(pedido, estado, rol, callbacks, motivo=""):
    with callbacks(execute=True):
        return cambiar_estado(pedido, estado, usuario=None, rol=rol, motivo=motivo)


# --- Criterio 1: confirmación --------------------------------------------------


def test_confirmar_envia_correo_con_desglose_domicilio_y_numero(m, pedido):
    assert len(mail.outbox) == 1
    correo = mail.outbox[0]
    assert correo.to == ["cli@correo.com"]
    assert pedido.numero_pedido in correo.subject
    for texto in ("Hamburguesa", "2 x", "Domicilio: $3.000", "Total: $", pedido.numero_pedido):
        assert texto in correo.body
    # Versión HTML adjunta (plantilla)
    html, tipo = correo.alternatives[0]
    assert tipo == "text/html"
    assert "Hamburguesa" in html and pedido.numero_pedido in html and "$3.000" in html


# --- Criterio 2: cambios de estado ----------------------------------------------


def test_envia_un_correo_en_cada_cambio_relevante(pedido, django_capture_on_commit_callbacks):
    esperado = [
        (E.RECIBIDO, "operador", "aprobado"),
        (E.EN_PREPARACION, "cocina", "en preparación"),
    ]
    for estado, rol, palabra in esperado:
        mail.outbox.clear()
        pedido = avanzar(pedido, estado, rol, django_capture_on_commit_callbacks)
        assert len(mail.outbox) == 1, estado
        assert palabra in mail.outbox[0].subject
        assert mail.outbox[0].to == ["cli@correo.com"]

    avanzar(pedido, E.LISTO_DESPACHO, "cocina", django_capture_on_commit_callbacks)
    pedido.refresh_from_db()
    for estado, palabra in ((E.RECOGIDO, None), (E.EN_CAMINO, "en camino"), (E.ENTREGADO, "entregado")):
        mail.outbox.clear()
        pedido = avanzar(pedido, estado, "repartidor", django_capture_on_commit_callbacks)
        if palabra:
            assert len(mail.outbox) == 1 and palabra in mail.outbox[0].subject
        else:
            assert mail.outbox == []  # "recogido" es un paso interno


def test_pasos_internos_no_envian_correo(pedido, django_capture_on_commit_callbacks):
    pedido = avanzar(pedido, E.RECIBIDO, "operador", django_capture_on_commit_callbacks)
    pedido = avanzar(pedido, E.EN_PREPARACION, "cocina", django_capture_on_commit_callbacks)
    mail.outbox.clear()
    avanzar(pedido, E.LISTO_DESPACHO, "cocina", django_capture_on_commit_callbacks)
    assert mail.outbox == []


# --- Criterio 3: cancelación con motivo -----------------------------------------


def test_cancelacion_explica_el_motivo(pedido, django_capture_on_commit_callbacks):
    mail.outbox.clear()
    avanzar(pedido, E.CANCELADO, "operador", django_capture_on_commit_callbacks, motivo="Sin stock de pan")

    assert len(mail.outbox) == 1
    correo = mail.outbox[0]
    assert "cancelado" in correo.subject
    assert "Motivo: Sin stock de pan" in correo.body
    assert "Sin stock de pan" in correo.alternatives[0][0]


# --- Criterio 5: un fallo de correo no bloquea nada ------------------------------


def test_si_falla_el_servidor_de_correo_el_estado_cambia_igual(
    pedido, monkeypatch, caplog, django_capture_on_commit_callbacks
):
    def falla(*args, **kwargs):
        raise ConnectionError("sin servidor de correo")

    monkeypatch.setattr("usuarios.tasks.send_mail", falla)
    mail.outbox.clear()

    with caplog.at_level(logging.ERROR):
        nuevo = avanzar(pedido, E.RECIBIDO, "operador", django_capture_on_commit_callbacks)

    pedido.refresh_from_db()
    assert nuevo.estado == pedido.estado == E.RECIBIDO
    assert pedido.historial_estados.filter(estado=E.RECIBIDO).exists()
    assert "No se pudo enviar el correo" in caplog.text


def test_si_falla_la_plantilla_el_estado_cambia_igual(
    pedido, monkeypatch, caplog, django_capture_on_commit_callbacks
):
    def falla(*args, **kwargs):
        raise RuntimeError("plantilla rota")

    monkeypatch.setattr("pedidos.correos.render_to_string", falla)
    mail.outbox.clear()

    with caplog.at_level(logging.ERROR):
        avanzar(pedido, E.RECIBIDO, "operador", django_capture_on_commit_callbacks)

    pedido.refresh_from_db()
    assert pedido.estado == E.RECIBIDO
    assert mail.outbox == []
    assert "No se pudo enviar el correo de estado" in caplog.text


def test_si_falla_el_correo_de_confirmacion_el_pedido_se_crea(m, monkeypatch, django_capture_on_commit_callbacks):
    monkeypatch.setattr("usuarios.tasks.send_mail", lambda **kw: (_ for _ in ()).throw(ConnectionError()))
    api = APIClient()
    api.force_authenticate(m.usuario)

    with django_capture_on_commit_callbacks(execute=True):
        respuesta = api.post(
            "/api/pedidos/confirmar/",
            {
                "sede_id": m.sede.pk, "direccion_id": m.direccion.pk, "metodo_pago": "efectivo",
                "items": [{"producto_id": m.producto.pk, "cantidad": 1}],
            },
            format="json",
        )

    assert respuesta.status_code == 201
    assert Pedido.objects.filter(cliente=m.cliente).count() == 1


# --- Casos límite ---------------------------------------------------------------


def test_pedido_sin_cliente_no_envia_correo_ni_falla(pedido, django_capture_on_commit_callbacks):
    Pedido.objects.filter(pk=pedido.pk).update(cliente=None)
    pedido.refresh_from_db()
    mail.outbox.clear()

    avanzar(pedido, E.RECIBIDO, "operador", django_capture_on_commit_callbacks)

    assert mail.outbox == []
