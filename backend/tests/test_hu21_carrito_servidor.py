"""Pruebas de HU-21 (producto final) · Carrito guardado en el servidor."""
from datetime import date

import pytest
from django.contrib.auth.models import Group
from rest_framework.test import APIClient

from usuarios.carrito import MAXIMO_LINEAS
from usuarios.models import CarritoGuardado, Cliente, Empleado, Usuario
from usuarios.roles import OPERADOR

pytestmark = pytest.mark.django_db

CARRITO = "/api/usuarios/carrito/"

LINEA = {
    "id": "a1",
    "producto": {"id": 3, "nombre": "Hamburguesa", "precio_base": "18000.00"},
    "tamano": None,
    "adiciones": [],
    "exclusiones": [],
    "cantidad": 2,
}


def crear_cliente(email, celular, documento):
    usuario = Usuario.objects.create_user(username=email, email=email, password="ClaveSegura2026")
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


def guardar(cliente, datos):
    return api_de(cliente.usuario).put(CARRITO, datos, format="json")


def test_sin_carrito_guardado_devuelve_carrito_vacio(laura):
    respuesta = api_de(laura.usuario).get(CARRITO)

    assert respuesta.status_code == 200
    assert respuesta.data == {"sedeId": None, "lineas": [], "promocion": None, "actualizado_en": None}


def test_guardar_y_consultar_el_carrito(laura):
    promocion = {"codigo": "BIENVENIDA", "tipo": "porcentaje", "valor": "10"}
    respuesta = guardar(laura, {"sedeId": 1, "lineas": [LINEA], "promocion": promocion})

    assert respuesta.status_code == 200
    assert respuesta.data["actualizado_en"] is not None

    consulta = api_de(laura.usuario).get(CARRITO)
    assert consulta.data["sedeId"] == 1
    assert consulta.data["lineas"] == [LINEA]
    assert consulta.data["promocion"] == promocion


def test_guardar_otra_vez_reemplaza_sin_duplicar(laura):
    guardar(laura, {"sedeId": 1, "lineas": [LINEA]})
    guardar(laura, {"sedeId": 2, "lineas": []})

    assert CarritoGuardado.objects.filter(cliente=laura).count() == 1
    consulta = api_de(laura.usuario).get(CARRITO)
    assert consulta.data["sedeId"] == 2
    assert consulta.data["lineas"] == []


def test_cada_cliente_ve_solo_su_carrito(laura, pedro):
    guardar(laura, {"sedeId": 1, "lineas": [LINEA]})

    assert api_de(pedro.usuario).get(CARRITO).data["lineas"] == []


def test_sin_sesion_responde_401():
    assert api_de().get(CARRITO).status_code == 401


def test_personal_no_tiene_carrito():
    usuario = Usuario.objects.create_user(username="op@correo.com", email="op@correo.com", password="x")
    usuario.groups.add(Group.objects.get_or_create(name=OPERADOR)[0])
    Empleado.objects.create(
        usuario=usuario, tipo_documento="CC", num_documento="2000000001", nombres="Ana",
        apellidos="Ruiz", celular="3000000000", direccion="Calle 1",
    )

    assert api_de(usuario).get(CARRITO).status_code == 403
    assert api_de(usuario).put(CARRITO, {"lineas": []}, format="json").status_code == 403


@pytest.mark.parametrize("datos", [
    {},                                   # falta lineas
    {"lineas": "no es lista"},
    {"lineas": [{"cantidad": 1}]},        # línea sin id
    {"lineas": [], "sedeId": "uno"},
    {"lineas": [], "promocion": "texto"},
])
def test_forma_invalida_responde_400(laura, datos):
    assert guardar(laura, datos).status_code == 400
    assert not CarritoGuardado.objects.filter(cliente=laura).exists()


def test_demasiadas_lineas_responde_400(laura):
    lineas = [{**LINEA, "id": str(i)} for i in range(MAXIMO_LINEAS + 1)]

    assert guardar(laura, {"lineas": lineas}).status_code == 400


def test_carrito_demasiado_grande_responde_400(laura):
    linea = {**LINEA, "observaciones": "x" * 60_000}

    respuesta = guardar(laura, {"lineas": [linea]})

    assert respuesta.status_code == 400
    assert "demasiado grande" in str(respuesta.data)
