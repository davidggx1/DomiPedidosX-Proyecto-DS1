from types import SimpleNamespace

import pytest
from django.contrib.auth.models import AnonymousUser, Group
from rest_framework.test import APIRequestFactory

from sedes.models import Ciudad, Sede
from usuarios.models import Empleado, Usuario
from usuarios.permissions import (
    EsAdministrador,
    EsCocina,
    EsPersonal,
    PerteneceALaSede,
)
from usuarios.roles import ADMINISTRADOR, COCINA, OPERADOR

pytestmark = pytest.mark.django_db


def _sede(nombre):
    ciudad, _ = Ciudad.objects.get_or_create(nombre="Cali")
    return Sede.objects.create(
        ciudad=ciudad, nombre=nombre, direccion="Calle 1 # 2-3",
        latitud=3.45, longitud=-76.53, barrio="Granada",
        telefono="3000000000", correo="s@correo.com",
    )


def _usuario(rol, email, sede=None):
    usuario = Usuario.objects.create_user(
        username=email, email=email, password="ClaveSegura2026"
    )
    if rol:
        usuario.groups.add(Group.objects.get_or_create(name=rol)[0])
    if sede:
        Empleado.objects.create(
            usuario=usuario, sede=sede, tipo_documento="CC",
            num_documento=email[:10], nombres="N", apellidos="A",
            celular="3001234567", direccion="Calle 4",
        )
    return usuario


def _request(usuario):
    request = APIRequestFactory().get("/x/")
    request.user = usuario
    return request


def test_es_administrador():
    sede = _sede("Norte")
    admin = _usuario(ADMINISTRADOR, "admin@correo.com")
    operador = _usuario(OPERADOR, "operador@correo.com", sede)
    permiso = EsAdministrador()
    assert permiso.has_permission(_request(admin), None)
    assert not permiso.has_permission(_request(operador), None)
    assert not permiso.has_permission(_request(AnonymousUser()), None)


def test_es_cocina_rechaza_otros_roles():
    sede = _sede("Norte")
    cocina = _usuario(COCINA, "cocina@correo.com", sede)
    operador = _usuario(OPERADOR, "operador@correo.com", sede)
    assert EsCocina().has_permission(_request(cocina), None)
    assert not EsCocina().has_permission(_request(operador), None)


def test_es_personal_excluye_clientes():
    sede = _sede("Norte")
    operador = _usuario(OPERADOR, "operador@correo.com", sede)
    cliente = _usuario(None, "cliente@correo.com")
    assert EsPersonal().has_permission(_request(operador), None)
    assert not EsPersonal().has_permission(_request(cliente), None)


def test_pertenece_a_la_sede():
    norte, sur = _sede("Norte"), _sede("Sur")
    operador = _usuario(OPERADOR, "operador@correo.com", norte)
    admin = _usuario(ADMINISTRADOR, "admin@correo.com")
    permiso, view = PerteneceALaSede(), SimpleNamespace()
    propio, ajeno = SimpleNamespace(sede=norte), SimpleNamespace(sede=sur)

    assert permiso.has_object_permission(_request(operador), view, propio)
    assert not permiso.has_object_permission(_request(operador), view, ajeno)
    assert permiso.has_object_permission(_request(admin), view, ajeno)


def test_pertenece_a_la_sede_con_campo_anidado():
    norte, sur = _sede("Norte"), _sede("Sur")
    operador = _usuario(OPERADOR, "operador@correo.com", norte)
    view = SimpleNamespace(campo_sede="pedido.sede")
    permiso = PerteneceALaSede()

    assert permiso.has_object_permission(
        _request(operador), view, SimpleNamespace(pedido=SimpleNamespace(sede=norte))
    )
    assert not permiso.has_object_permission(
        _request(operador), view, SimpleNamespace(pedido=SimpleNamespace(sede=sur))
    )


def test_los_grupos_de_roles_existen_por_migracion():
    nombres = set(Group.objects.values_list("name", flat=True))
    assert {"administrador", "operador", "cocina", "repartidor"} <= nombres