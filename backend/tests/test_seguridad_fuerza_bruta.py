"""
Seguridad · Fuerza bruta en el login (Clase 10, diapositivas 19 y 43).

- Límite por IP (ScopedRateThrottle, alcance "login") en login, login de personal
  y restablecimiento de contraseña: pasado el límite responde 429 en español.
- Bloqueo por correo tras LOGIN_FAILS_LIMIT contraseñas malas; un login exitoso
  borra el contador.
- Cada fallo y cada bloqueo quedan en el log con correo e IP, nunca la contraseña.
"""
import logging

import pytest
from django.contrib.auth.models import Group
from django.core.cache import cache
from rest_framework.test import APIClient
from rest_framework.throttling import ScopedRateThrottle

from sedes.models import Ciudad, Sede
from usuarios.intentos_login import MENSAJE_DEMASIADOS_INTENTOS
from usuarios.models import Empleado, Usuario
from usuarios.roles import OPERADOR

pytestmark = pytest.mark.django_db

LOGIN = "/api/usuarios/login/"
LOGIN_PERSONAL = "/api/usuarios/login-personal/"
TOKEN = "/api/auth/token/"
SOLICITAR = "/api/usuarios/contrasena/solicitar/"
RESTABLECER = "/api/usuarios/contrasena/restablecer/"
EMAIL = "ana@correo.com"
PASSWORD = "ClaveSegura2026"
CLAVE_MALA = "ClaveEquivocada-123"


@pytest.fixture
def client():
    return APIClient()


@pytest.fixture
def usuario():
    return Usuario.objects.create_user(username=EMAIL, email=EMAIL, password=PASSWORD)


@pytest.fixture
def sin_limite_por_ip(monkeypatch):
    """
    Para probar el bloqueo por correo sin que antes salte el límite por IP.
    DRF copia DEFAULT_THROTTLE_RATES en la clase al importarla, por eso se cambia ahí.
    """
    monkeypatch.setattr(ScopedRateThrottle, "THROTTLE_RATES", {"login": "1000/min"})


def entrar(client, password, url=LOGIN, email=EMAIL, ip="10.0.0.1"):
    return client.post(url, {"email": email, "password": password}, format="json", REMOTE_ADDR=ip)


# --- Límite por IP -------------------------------------------------------------


@pytest.mark.parametrize("url", [LOGIN, LOGIN_PERSONAL, TOKEN])
def test_sexta_peticion_de_login_en_un_minuto_responde_429(client, usuario, url):
    for _ in range(5):
        assert entrar(client, CLAVE_MALA, url).status_code == 401

    respuesta = entrar(client, CLAVE_MALA, url)

    assert respuesta.status_code == 429
    assert respuesta.data["detail"].startswith(MENSAJE_DEMASIADOS_INTENTOS)
    assert "segundos" in respuesta.data["detail"]
    assert "Retry-After" in respuesta.headers


def test_el_limite_es_por_ip(client, usuario):
    for _ in range(5):
        entrar(client, CLAVE_MALA, email="otro@correo.com", ip="10.0.0.1")

    assert entrar(client, CLAVE_MALA, email="otro@correo.com", ip="10.0.0.1").status_code == 429
    assert entrar(client, PASSWORD, ip="10.0.0.2").status_code == 200


def test_restablecer_contrasena_tambien_tiene_limite(client, usuario):
    for _ in range(3):
        assert client.post(SOLICITAR, {"email": EMAIL}, format="json").status_code == 200
    for _ in range(2):
        assert client.post(RESTABLECER, {"uid": "x", "token": "y", "password": "z"}, format="json").status_code == 400

    assert client.post(SOLICITAR, {"email": EMAIL}, format="json").status_code == 429
    assert client.post(RESTABLECER, {"uid": "x", "token": "y", "password": "z"}, format="json").status_code == 429


# --- Bloqueo por correo ---------------------------------------------------------


def test_cinco_fallos_bloquean_el_correo_aunque_cambie_la_ip(client, usuario, sin_limite_por_ip):
    for intento in range(5):
        assert entrar(client, CLAVE_MALA, ip=f"10.0.0.{intento}").status_code == 401

    # Ni con la contraseña correcta ni desde otra IP: está bloqueado.
    respuesta = entrar(client, PASSWORD, ip="10.9.9.9")
    assert respuesta.status_code == 429
    assert respuesta.data["detail"].startswith(MENSAJE_DEMASIADOS_INTENTOS)
    # Otro correo no se ve afectado.
    Usuario.objects.create_user(username="beto@correo.com", email="beto@correo.com", password=PASSWORD)
    assert entrar(client, PASSWORD, email="beto@correo.com").status_code == 200


def test_el_bloqueo_no_distingue_mayusculas(client, usuario, sin_limite_por_ip):
    for _ in range(5):
        entrar(client, CLAVE_MALA, email="ANA@correo.com")

    assert entrar(client, PASSWORD, email="ana@CORREO.com").status_code == 429


def test_el_bloqueo_vence_y_dura_lo_configurado(client, usuario, sin_limite_por_ip):
    for _ in range(5):
        entrar(client, CLAVE_MALA)
    respuesta = entrar(client, PASSWORD)
    assert respuesta.status_code == 429
    assert respuesta.headers["Retry-After"] == "300"

    cache.delete("login-fallos:ana@correo.com")  # como si pasaran los 5 minutos
    assert entrar(client, PASSWORD).status_code == 200


def test_login_exitoso_borra_el_contador(client, usuario, sin_limite_por_ip):
    for _ in range(4):
        entrar(client, CLAVE_MALA)
    assert entrar(client, PASSWORD).status_code == 200

    # Si el contador siguiera en 4, el siguiente fallo bloquearía la cuenta.
    for _ in range(4):
        assert entrar(client, CLAVE_MALA).status_code == 401
    assert entrar(client, PASSWORD).status_code == 200


def test_los_fallos_cuentan_igual_en_el_login_de_personal(client, sede_y_operador, sin_limite_por_ip):
    for _ in range(5):
        assert entrar(client, CLAVE_MALA, LOGIN_PERSONAL, email="op@correo.com").status_code == 401

    assert entrar(client, PASSWORD, LOGIN_PERSONAL, email="op@correo.com").status_code == 429
    # Cambiar de endpoint no sirve para saltarse el bloqueo.
    assert entrar(client, PASSWORD, LOGIN, email="op@correo.com").status_code == 429


def test_cliente_en_login_de_personal_no_cuenta_como_fallo(client, usuario, sin_limite_por_ip):
    """El frontend prueba primero el login de personal: la contraseña del cliente es correcta."""
    for _ in range(6):
        respuesta = entrar(client, PASSWORD, LOGIN_PERSONAL)
        assert respuesta.status_code == 401
        assert respuesta.data["code"] == "no_es_personal"

    assert entrar(client, PASSWORD).status_code == 200


@pytest.fixture
def sede_y_operador():
    ciudad = Ciudad.objects.create(nombre="Cali")
    sede = Sede.objects.create(
        ciudad=ciudad, nombre="Sede Norte", direccion="Calle 1 # 2-3", latitud=3.45, longitud=-76.53,
        barrio="Granada", telefono="3000000000", correo="norte@correo.com",
    )
    usuario = Usuario.objects.create_user(username="op@correo.com", email="op@correo.com", password=PASSWORD)
    usuario.groups.add(Group.objects.get_or_create(name=OPERADOR)[0])
    Empleado.objects.create(
        usuario=usuario, sede=sede, tipo_documento="CC", num_documento="111", nombres="Op",
        apellidos="Erador", celular="3001234567", direccion="Calle 4",
    )
    return usuario


# --- Registro en el log (diapositiva 19) ------------------------------------------


def test_cada_fallo_y_el_bloqueo_quedan_en_el_log_sin_la_contrasena(client, usuario, sin_limite_por_ip, caplog):
    with caplog.at_level(logging.WARNING, logger="usuarios.intentos_login"):
        for _ in range(5):
            entrar(client, CLAVE_MALA, ip="10.1.2.3")
        entrar(client, PASSWORD, ip="10.1.2.3")

    mensajes = [r.getMessage() for r in caplog.records if r.name == "usuarios.intentos_login"]
    assert len([m for m in mensajes if m.startswith("Intento de login fallido")]) == 4
    assert any(m.startswith("Cuenta bloqueada") for m in mensajes)
    assert any(m.startswith("Login rechazado") for m in mensajes)
    assert all(EMAIL in m and "10.1.2.3" in m for m in mensajes)
    assert not any(CLAVE_MALA in m or PASSWORD in m for m in mensajes)
