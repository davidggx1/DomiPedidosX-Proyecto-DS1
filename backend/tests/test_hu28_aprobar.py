import pytest
from django.contrib.auth.models import Group
from rest_framework.test import APIClient

from pedidos import aprobacion
from pedidos.models import EstadoPedido, HistorialEstadoPedido, Pedido
from sedes.models import Ciudad, Sede
from usuarios.models import Empleado, Usuario

pytestmark = pytest.mark.django_db


def _sede(nombre):
    ciudad, _ = Ciudad.objects.get_or_create(nombre="Cali")
    return Sede.objects.create(
        ciudad=ciudad, nombre=nombre, direccion="Calle 1 # 2-3", latitud=3.45,
        longitud=-76.53, barrio="Granada", telefono="3000000000", correo="s@correo.com",
    )


def _personal(rol, email, sede=None):
    usuario = Usuario.objects.create_user(
        username=email, email=email, password="ClaveSegura2026"
    )
    usuario.groups.add(Group.objects.get_or_create(name=rol)[0])
    if sede:
        Empleado.objects.create(
            usuario=usuario, sede=sede, tipo_documento="CC", num_documento=email[:10],
            nombres="N", apellidos="A", celular="3001234567", direccion="Calle 4",
        )
    return usuario


def _pedido(sede, numero="P-1", estado=EstadoPedido.PENDIENTE_APROBACION):
    return Pedido.objects.create(numero_pedido=numero, sede=sede, estado=estado)


def _url(pedido):
    return f"/api/pedidos/{pedido.pk}/aprobar/"


def _cliente_http(usuario):
    c = APIClient()
    c.force_authenticate(user=usuario)
    return c


def test_operador_aprueba_y_queda_auditado(monkeypatch):
    llamadas = []
    monkeypatch.setattr(aprobacion, "notificar_pedido", llamadas.append)
    sede = _sede("Norte")
    operador = _personal("operador", "op@correo.com", sede)
    pedido = _pedido(sede)

    r = _cliente_http(operador).patch(_url(pedido), format="json")

    assert r.status_code == 200
    assert r.data["estado"] == EstadoPedido.RECIBIDO
    assert r.data["aprobado_por"] == "op@correo.com"
    assert r.data["fecha_aprobacion"] is not None
    pedido.refresh_from_db()
    assert pedido.estado == EstadoPedido.RECIBIDO
    registro = HistorialEstadoPedido.objects.get(pedido=pedido)
    assert registro.usuario == operador
    assert registro.estado == EstadoPedido.RECIBIDO
    assert registro.fecha_hora is not None
    assert llamadas == [pedido]


def test_administrador_puede_aprobar_de_cualquier_sede():
    pedido = _pedido(_sede("Sur"))
    admin = _personal("administrador", "admin@correo.com")
    r = _cliente_http(admin).patch(_url(pedido), format="json")
    assert r.status_code == 200


def test_operador_no_aprueba_pedido_de_otra_sede():
    norte, sur = _sede("Norte"), _sede("Sur")
    operador = _personal("operador", "op@correo.com", norte)
    pedido = _pedido(sur)

    r = _cliente_http(operador).patch(_url(pedido), format="json")

    assert r.status_code == 404
    pedido.refresh_from_db()
    assert pedido.estado == EstadoPedido.PENDIENTE_APROBACION
    assert not HistorialEstadoPedido.objects.exists()


def test_segunda_aprobacion_responde_409_sin_duplicar_historial():
    sede = _sede("Norte")
    operador = _personal("operador", "op@correo.com", sede)
    pedido = _pedido(sede)
    c = _cliente_http(operador)

    assert c.patch(_url(pedido), format="json").status_code == 200
    r = c.patch(_url(pedido), format="json")

    assert r.status_code == 409
    assert r.data["estado_actual"] == EstadoPedido.RECIBIDO
    assert HistorialEstadoPedido.objects.filter(pedido=pedido).count() == 1


@pytest.mark.parametrize("estado", [EstadoPedido.CANCELADO, EstadoPedido.EN_PREPARACION])
def test_solo_se_aprueban_pedidos_pendientes(estado):
    sede = _sede("Norte")
    operador = _personal("operador", "op@correo.com", sede)
    pedido = _pedido(sede, estado=estado)
    r = _cliente_http(operador).patch(_url(pedido), format="json")
    assert r.status_code == 409
    pedido.refresh_from_db()
    assert pedido.estado == estado


def test_pedido_inexistente():
    operador = _personal("operador", "op@correo.com", _sede("Norte"))
    r = _cliente_http(operador).patch("/api/pedidos/99999/aprobar/", format="json")
    assert r.status_code == 404


def test_cocina_y_cliente_no_pueden_aprobar():
    sede = _sede("Norte")
    pedido = _pedido(sede)
    cocina = _personal("cocina", "cocina@correo.com", sede)
    cliente = Usuario.objects.create_user(
        username="c@correo.com", email="c@correo.com", password="ClaveSegura2026"
    )
    assert _cliente_http(cocina).patch(_url(pedido), format="json").status_code == 403
    assert _cliente_http(cliente).patch(_url(pedido), format="json").status_code == 403


def test_sin_token_responde_401():
    pedido = _pedido(_sede("Norte"))
    assert APIClient().patch(_url(pedido), format="json").status_code == 401