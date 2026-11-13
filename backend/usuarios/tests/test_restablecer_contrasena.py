"""Pruebas de HU-05 · Restablecer contraseña."""
import re
from datetime import datetime, timedelta
from unittest import mock

import pytest
from django.contrib.auth.tokens import default_token_generator
from django.core import mail
from rest_framework.test import APIClient

from usuarios.models import Cliente, Usuario

pytestmark = pytest.mark.django_db

SOLICITAR = "/api/usuarios/contrasena/solicitar/"
RESTABLECER = "/api/usuarios/contrasena/restablecer/"
LOGIN = "/api/auth/token/"
CLAVE_VIEJA = "ClaveSegura2026"
CLAVE_NUEVA = "OtraClaveSegura#2026"


@pytest.fixture
def client():
    return APIClient()


@pytest.fixture
def usuario():
    usuario = Usuario.objects.create_user(username="ana@correo.com", email="ana@correo.com", password=CLAVE_VIEJA)
    Cliente.objects.create(
        usuario=usuario, tipo_documento="CC", num_documento="123", nombres="Ana",
        apellidos="Prueba", celular="3001234567", fecha_nacimiento="2000-01-01",
    )
    return usuario


def enlace_del_correo():
    """uid y token del enlace que llegó en el último correo."""
    encontrado = re.search(r"/restablecer-contrasena\?uid=([\w-]+)&token=([\w-]+)", mail.outbox[-1].body)
    return {"uid": encontrado.group(1), "token": encontrado.group(2)}


def puede_entrar(client, password):
    return client.post(LOGIN, {"email": "ana@correo.com", "password": password}, format="json").status_code == 200


# --- Criterio 1: solicitud con mensaje idéntico ---------------------------------


def test_envia_el_enlace_si_el_correo_existe(client, usuario):
    r = client.post(SOLICITAR, {"email": "ANA@correo.com"}, format="json")

    assert r.status_code == 200
    assert len(mail.outbox) == 1
    assert mail.outbox[0].to == ["ana@correo.com"]
    assert "Hola Ana" in mail.outbox[0].body
    assert "http://localhost:5173/restablecer-contrasena?uid=" in mail.outbox[0].body


def test_mismo_mensaje_si_el_correo_no_existe_o_la_cuenta_esta_inactiva(client, usuario):
    existe = client.post(SOLICITAR, {"email": "ana@correo.com"}, format="json")
    mail.outbox.clear()
    no_existe = client.post(SOLICITAR, {"email": "nadie@correo.com"}, format="json")
    usuario.is_active = False
    usuario.save()
    inactiva = client.post(SOLICITAR, {"email": "ana@correo.com"}, format="json")

    assert no_existe.status_code == inactiva.status_code == existe.status_code == 200
    assert no_existe.data == inactiva.data == existe.data
    assert mail.outbox == []


def test_si_falla_el_correo_la_respuesta_no_cambia(client, usuario):
    with mock.patch("usuarios.tasks.send_mail", side_effect=ConnectionError("sin servidor")):
        r = client.post(SOLICITAR, {"email": "ana@correo.com"}, format="json")
    assert r.status_code == 200


def test_el_correo_es_obligatorio(client):
    assert client.post(SOLICITAR, {"email": "no-es-correo"}, format="json").status_code == 400


# --- Criterio 2: nueva contraseña ------------------------------------------------


def test_cambia_la_contrasena_y_la_anterior_deja_de_servir(client, usuario):
    client.post(SOLICITAR, {"email": "ana@correo.com"}, format="json")

    r = client.post(RESTABLECER, {**enlace_del_correo(), "password": CLAVE_NUEVA}, format="json")

    assert r.status_code == 200
    assert puede_entrar(client, CLAVE_NUEVA)
    assert not puede_entrar(client, CLAVE_VIEJA)
    usuario.refresh_from_db()
    assert usuario.password.startswith("pbkdf2_")  # guardada con hash


@pytest.mark.parametrize("password", ["Corta1#", "12345678901", "password123"])
def test_rechaza_contrasenas_debiles(client, usuario, password):
    client.post(SOLICITAR, {"email": "ana@correo.com"}, format="json")

    r = client.post(RESTABLECER, {**enlace_del_correo(), "password": password}, format="json")

    assert r.status_code == 400
    assert "password" in r.data
    assert puede_entrar(client, CLAVE_VIEJA)


# --- Criterio 3: el token vence a la hora o al primer uso ------------------------


def test_el_enlace_solo_sirve_una_vez(client, usuario):
    client.post(SOLICITAR, {"email": "ana@correo.com"}, format="json")
    enlace = enlace_del_correo()
    assert client.post(RESTABLECER, {**enlace, "password": CLAVE_NUEVA}, format="json").status_code == 200

    r = client.post(RESTABLECER, {**enlace, "password": "TerceraClave#2026"}, format="json")

    assert r.status_code == 400
    assert "expiró" in r.data["detail"][0]
    assert puede_entrar(client, CLAVE_NUEVA)


# El generador de tokens de Django mide el tiempo con datetime.now() (hora local sin zona).
def test_el_enlace_vence_despues_de_una_hora(client, usuario):
    client.post(SOLICITAR, {"email": "ana@correo.com"}, format="json")
    enlace = enlace_del_correo()
    dentro_de = datetime.now() + timedelta(hours=1, minutes=1)

    with mock.patch.object(default_token_generator, "_now", return_value=dentro_de):
        r = client.post(RESTABLECER, {**enlace, "password": CLAVE_NUEVA}, format="json")

    assert r.status_code == 400
    assert puede_entrar(client, CLAVE_VIEJA)


def test_antes_de_la_hora_sigue_sirviendo(client, usuario):
    client.post(SOLICITAR, {"email": "ana@correo.com"}, format="json")
    enlace = enlace_del_correo()
    dentro_de = datetime.now() + timedelta(minutes=59)

    with mock.patch.object(default_token_generator, "_now", return_value=dentro_de):
        r = client.post(RESTABLECER, {**enlace, "password": CLAVE_NUEVA}, format="json")

    assert r.status_code == 200


@pytest.mark.parametrize("uid,token", [("basura", "basura"), ("MQ", "token-falso")])
def test_rechaza_enlaces_invalidos(client, usuario, uid, token):
    r = client.post(RESTABLECER, {"uid": uid, "token": token, "password": CLAVE_NUEVA}, format="json")
    assert r.status_code == 400
    assert puede_entrar(client, CLAVE_VIEJA)


def test_una_cuenta_desactivada_no_puede_restablecer(client, usuario):
    client.post(SOLICITAR, {"email": "ana@correo.com"}, format="json")
    enlace = enlace_del_correo()
    usuario.is_active = False
    usuario.save()

    assert client.post(RESTABLECER, {**enlace, "password": CLAVE_NUEVA}, format="json").status_code == 400
