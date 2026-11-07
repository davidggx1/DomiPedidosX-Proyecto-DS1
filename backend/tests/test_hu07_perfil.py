"""Pruebas de HU-07 · Editar perfil y datos de contacto (SCRUM-102)."""
from datetime import date

import pytest
from django.contrib.auth.models import Group
from rest_framework.test import APIClient

from usuarios.models import Cliente, Usuario
from usuarios.roles import OPERADOR

pytestmark = pytest.mark.django_db

PERFIL = "/api/usuarios/perfil/"
CLAVE = "ClaveSegura2026"


def crear_cliente(email, celular, documento):
    usuario = Usuario.objects.create_user(username=email, email=email, password=CLAVE)
    return Cliente.objects.create(
        usuario=usuario, tipo_documento="CC", num_documento=documento, nombres="Laura",
        apellidos="Gómez", celular=celular, fecha_nacimiento=date(2000, 1, 1),
    )


@pytest.fixture
def laura():
    return crear_cliente("laura@correo.com", "3101112233", "1000000001")


@pytest.fixture
def pedro():
    return crear_cliente("pedro@correo.com", "3104445566", "1000000002")


def api_de(usuario=None):
    api = APIClient()
    if usuario is not None:
        api.force_authenticate(usuario)
    return api


def editar(cliente, datos):
    return api_de(cliente.usuario).patch(PERFIL, datos, format="json")


# --- Consultar el perfil --------------------------------------------------------


def test_cliente_consulta_su_perfil(laura):
    respuesta = api_de(laura.usuario).get(PERFIL)

    assert respuesta.status_code == 200
    assert respuesta.data == {
        "email": "laura@correo.com",
        "nombres": "Laura",
        "apellidos": "Gómez",
        "celular": "3101112233",
        "tipo_documento": "CC",
        "num_documento": "1000000001",
        "fecha_nacimiento": "2000-01-01",
    }


# --- Criterio: actualizar nombre y teléfono -------------------------------------


def test_cliente_actualiza_nombres_y_apellidos(laura):
    respuesta = editar(laura, {"nombres": "Laura Marcela", "apellidos": "Gómez Ruiz"})

    assert respuesta.status_code == 200
    laura.refresh_from_db()
    assert (laura.nombres, laura.apellidos) == ("Laura Marcela", "Gómez Ruiz")


def test_cliente_actualiza_su_celular(laura):
    respuesta = editar(laura, {"celular": "3209998877"})

    assert respuesta.status_code == 200
    assert respuesta.data["celular"] == "3209998877"
    laura.refresh_from_db()
    assert laura.celular == "3209998877"


def test_nombres_vacios_no_se_aceptan(laura):
    respuesta = editar(laura, {"nombres": "   "})

    assert respuesta.status_code == 400
    assert respuesta.data["nombres"] == ["Escribe tus nombres."]


# --- Criterio: re-validación del teléfono (reglas de HU-02) ---------------------


@pytest.mark.parametrize("celular", ["310111223", "31011122334", "310-111-22", "abcdefghij"])
def test_celular_con_formato_invalido_responde_400(laura, celular):
    respuesta = editar(laura, {"celular": celular})

    assert respuesta.status_code == 400
    assert "celular" in respuesta.data
    laura.refresh_from_db()
    assert laura.celular == "3101112233"


def test_celular_de_otro_cliente_responde_400(laura, pedro):
    respuesta = editar(laura, {"celular": pedro.celular})

    assert respuesta.status_code == 400
    assert respuesta.data["celular"] == ["Este número de teléfono ya está registrado en otra cuenta."]


def test_guardar_el_mismo_celular_no_es_un_duplicado(laura):
    respuesta = editar(laura, {"nombres": "Laura", "celular": "3101112233"})

    assert respuesta.status_code == 200


# --- Lo que no se edita aquí ---------------------------------------------------


def test_correo_y_documento_no_se_modifican(laura):
    respuesta = editar(
        laura,
        {"email": "otro@correo.com", "num_documento": "999", "fecha_nacimiento": "1990-05-05"},
    )

    assert respuesta.status_code == 200
    laura.refresh_from_db()
    laura.usuario.refresh_from_db()
    assert laura.usuario.email == "laura@correo.com"
    assert laura.num_documento == "1000000001"
    assert laura.fecha_nacimiento == date(2000, 1, 1)


def test_put_no_esta_permitido(laura):
    respuesta = api_de(laura.usuario).put(PERFIL, {"nombres": "X"}, format="json")

    assert respuesta.status_code == 405


# --- Permisos -------------------------------------------------------------------


def test_sin_sesion_responde_401():
    assert api_de().get(PERFIL).status_code == 401


def test_el_personal_no_tiene_perfil_de_cliente():
    operador = Usuario.objects.create_user(
        username="operador@correo.com", email="operador@correo.com", password=CLAVE
    )
    operador.groups.add(Group.objects.get_or_create(name=OPERADOR)[0])

    assert api_de(operador).get(PERFIL).status_code == 403
    assert api_de(operador).patch(PERFIL, {"nombres": "X"}, format="json").status_code == 403
