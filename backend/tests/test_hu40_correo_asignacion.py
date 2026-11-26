"""HU-40 (ampliación) · Correo al repartidor cuando se le asigna un pedido.

Sección 4.7 del proyecto: el repartidor recibe la asignación; el cliente, la salida
"En camino" (ese correo ahora dice el primer nombre de quien lleva el pedido).
"""
from datetime import date
from decimal import Decimal

import pytest
from django.contrib.auth.models import Group
from django.core import mail

from pedidos.asignacion import asignar, retirar
from pedidos.estados import cambiar_estado
from pedidos.models import EstadoFactura, EstadoPedido as E, Factura, MetodoPago, Pedido
from sedes.models import Ciudad, Sede
from usuarios.models import Cliente, Empleado, Repartidor, Usuario
from usuarios.roles import REPARTIDOR

pytestmark = pytest.mark.django_db


@pytest.fixture
def sede():
    ciudad, _ = Ciudad.objects.get_or_create(nombre="Cali")
    return Sede.objects.create(
        ciudad=ciudad, nombre="Centro", direccion="Calle 1 # 2-3", latitud=3.45, longitud=-76.53,
        barrio="Granada", telefono="3000000000", correo="centro@correo.com",
    )


def _repartidor(sede, email, nombres="Carlos Andrés"):
    usuario = Usuario.objects.create_user(username=email, email=email, password="x")
    usuario.groups.add(Group.objects.get_or_create(name=REPARTIDOR)[0])
    empleado = Empleado.objects.create(
        usuario=usuario, sede=sede, tipo_documento="CC", num_documento=email[:10], nombres=nombres,
        apellidos="Ruiz", celular="3001234567", direccion="Calle 4",
    )
    return Repartidor.objects.create(empleado=empleado, disponible=True)


@pytest.fixture
def carlos(sede):
    return _repartidor(sede, "carlos@correo.com")


@pytest.fixture
def ana():
    usuario = Usuario.objects.create_user(username="ana@correo.com", email="ana@correo.com", password="x")
    return Cliente.objects.create(
        usuario=usuario, tipo_documento="CC", num_documento="1010", nombres="Ana", apellidos="Gómez",
        celular="3009998877", fecha_nacimiento=date(2000, 1, 1),
    )


def _pedido(sede, cliente, metodo=MetodoPago.EFECTIVO, pagada=False):
    pedido = Pedido.objects.create(
        sede=sede, cliente=cliente, numero_pedido="P-100", estado=E.LISTO_DESPACHO,
        entrega_direccion="Calle 5 # 10-20", entrega_barrio="San Fernando",
    )
    Factura.objects.create(
        pedido=pedido, numero="F-100", subtotal=Decimal("35000"), iva=Decimal("0"),
        costo_domicilio=Decimal("0"), total=Decimal("35000"), metodo_pago=metodo,
        estado_factura=EstadoFactura.PAGADA if pagada else EstadoFactura.PENDIENTE,
    )
    return pedido


def _asignar(pedido, repartidor, callbacks):
    mail.outbox.clear()
    with callbacks(execute=True):
        asignar(pedido, repartidor)
    pedido.refresh_from_db()
    return pedido


def test_al_asignar_le_llega_un_correo_al_repartidor(sede, carlos, ana, django_capture_on_commit_callbacks):
    pedido = _pedido(sede, ana)

    _asignar(pedido, carlos, django_capture_on_commit_callbacks)

    assert len(mail.outbox) == 1
    correo = mail.outbox[0]
    assert correo.to == ["carlos@correo.com"]
    assert correo.subject == "Se te asignó el pedido P-100"
    for texto in ("Hola Carlos,", "Centro (Calle 1 # 2-3)", "Calle 5 # 10-20, San Fernando",
                  "$35.000 · Efectivo (cóbralo al entregar)", f"/repartidor/entregas/{pedido.pk}"):
        assert texto in correo.body
    html = correo.alternatives[0][0]
    assert "Ver la entrega" in html and "Ver mi pedido" not in html


def test_si_ya_esta_pagado_no_pide_cobrar(sede, carlos, ana, django_capture_on_commit_callbacks):
    pedido = _pedido(sede, ana, metodo=MetodoPago.TARJETA, pagada=True)

    _asignar(pedido, carlos, django_capture_on_commit_callbacks)

    assert "(ya está pagado)" in mail.outbox[0].body


def test_al_reasignar_le_llega_al_nuevo_repartidor(sede, carlos, ana, django_capture_on_commit_callbacks):
    luz = _repartidor(sede, "luz@correo.com", nombres="Luz")
    pedido = _asignar(_pedido(sede, ana), carlos, django_capture_on_commit_callbacks)
    with django_capture_on_commit_callbacks(execute=True):
        retirar(pedido)
    pedido.refresh_from_db()

    _asignar(pedido, luz, django_capture_on_commit_callbacks)

    assert [c.to for c in mail.outbox] == [["luz@correo.com"]]


def test_retirar_no_envia_correo(sede, carlos, ana, django_capture_on_commit_callbacks):
    pedido = _asignar(_pedido(sede, ana), carlos, django_capture_on_commit_callbacks)
    mail.outbox.clear()

    with django_capture_on_commit_callbacks(execute=True):
        retirar(pedido)

    assert mail.outbox == []


def test_un_fallo_del_correo_no_rompe_la_asignacion(sede, carlos, ana, django_capture_on_commit_callbacks,
                                                     monkeypatch):
    def falla(*args, **kwargs):
        raise RuntimeError("SMTP caído")

    monkeypatch.setattr("pedidos.correos.encolar_correo", falla)
    pedido = _asignar(_pedido(sede, ana), carlos, django_capture_on_commit_callbacks)

    assert pedido.repartidor_id == carlos.pk


def test_el_correo_en_camino_del_cliente_dice_quien_lo_lleva(sede, carlos, ana,
                                                             django_capture_on_commit_callbacks):
    pedido = _asignar(_pedido(sede, ana), carlos, django_capture_on_commit_callbacks)
    with django_capture_on_commit_callbacks(execute=True):
        pedido = cambiar_estado(pedido, E.RECOGIDO, usuario=None, rol="repartidor")
    mail.outbox.clear()

    with django_capture_on_commit_callbacks(execute=True):
        cambiar_estado(pedido, E.EN_CAMINO, usuario=None, rol="repartidor")

    assert len(mail.outbox) == 1
    correo = mail.outbox[0]
    assert correo.to == ["ana@correo.com"]
    assert "Carlos salió de Centro con tu pedido y va hacia tu dirección." in correo.body
    assert "Ruiz" not in correo.body
