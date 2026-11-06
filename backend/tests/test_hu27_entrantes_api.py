import pytest
from django.contrib.auth.models import Group
from rest_framework.test import APIClient

from pedidos.models import EstadoPedido, Pedido
from sedes.models import Ciudad, Sede
from usuarios.models import Empleado, Usuario

URL = "/api/pedidos/entrantes/"
pytestmark = pytest.mark.django_db


def _sede(nombre):
    ciudad, _ = Ciudad.objects.get_or_create(nombre="Cali")
    return Sede.objects.create(
        ciudad=ciudad, nombre=nombre, direccion="Calle 1 # 2-3", latitud=3.45,
        longitud=-76.53, barrio="Granada", telefono="3000000000", correo="s@correo.com",
    )


def _personal(rol, email, sede=None):
    usuario = Usuario.objects.create_user(username=email, email=email, password="ClaveSegura2026")
    usuario.groups.add(Group.objects.get_or_create(name=rol)[0])
    if sede:
        Empleado.objects.create(
            usuario=usuario, sede=sede, tipo_documento="CC", num_documento=email[:10],
            nombres="N", apellidos="A", celular="3001234567", direccion="Calle 4",
        )
    return usuario


def _pedido(sede, numero, estado=EstadoPedido.PENDIENTE_APROBACION):
    return Pedido.objects.create(numero_pedido=numero, sede=sede, estado=estado)


def test_lista_filtrada_por_sede_ordenada_y_solo_pendientes():
    norte, sur = _sede("Norte"), _sede("Sur")
    operador = _personal("operador", "op_norte@correo.com", norte)
    _pedido(norte, "P-1")
    _pedido(norte, "P-2")
    _pedido(sur, "P-3")
    _pedido(norte, "P-4", estado=EstadoPedido.RECIBIDO)

    client = APIClient()
    client.force_authenticate(user=operador)
    response = client.get(URL)

    assert response.status_code == 200
    assert [p["numero_pedido"] for p in response.data] == ["P-1", "P-2"]


def test_administrador_ve_todas_las_sedes():
    norte, sur = _sede("Norte"), _sede("Sur")
    admin = _personal("administrador", "admin@correo.com")
    _pedido(norte, "P-1")
    _pedido(sur, "P-2")

    client = APIClient()
    client.force_authenticate(user=admin)
    assert len(client.get(URL).data) == 2


def test_cliente_y_cocina_no_acceden():
    sede = _sede("Norte")
    cocina = _personal("cocina", "cocina@correo.com", sede)
    client = APIClient()
    client.force_authenticate(user=cocina)
    assert client.get(URL).status_code == 403


def test_sin_token_responde_401():
    assert APIClient().get(URL).status_code == 401