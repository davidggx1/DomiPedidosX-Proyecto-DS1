"""
Pasos de tests/features/iniciar_sesion.feature (HU-03 + protección contra fuerza bruta).

El límite por IP (5 peticiones por minuto) se sube aquí para probar solo el bloqueo
por cuenta: así el escenario de "5 fallos" mide la regla de la cuenta y no la de la IP,
que ya tiene sus propias pruebas en test_seguridad_fuerza_bruta.py.
"""
from types import SimpleNamespace

import pytest
from pytest_bdd import given, parsers, scenarios, then, when
from rest_framework.test import APIClient
from rest_framework.throttling import ScopedRateThrottle

from usuarios.models import Usuario

pytestmark = pytest.mark.django_db

scenarios("features/iniciar_sesion.feature")

LOGIN = "/api/usuarios/login/"
CLAVE = "ClaveSegura2026"
CLAVE_MALA = "ClaveEquivocada-123"


@given(parsers.parse('que tengo una cuenta con el correo "{email}"'), target_fixture="ctx")
def cuenta(email, monkeypatch):
    monkeypatch.setattr(ScopedRateThrottle, "THROTTLE_RATES", {"login": "1000/min"})
    usuario = Usuario.objects.create_user(username=email, email=email, password=CLAVE)
    return SimpleNamespace(usuario=usuario, email=email, api=APIClient(), respuesta=None)


def entrar(ctx, password, email=None):
    return ctx.api.post(LOGIN, {"email": email or ctx.email, "password": password}, format="json")


@given("que el administrador desactivó mi cuenta")
def cuenta_inactiva(ctx):
    ctx.usuario.is_active = False
    ctx.usuario.save()


@given(parsers.parse("que me equivoqué de contraseña {fallos:d} veces seguidas"))
def fallos_seguidos(ctx, fallos):
    for _ in range(fallos):
        assert entrar(ctx, CLAVE_MALA).status_code == 401


@when("inicio sesión con mi contraseña")
def con_mi_clave(ctx):
    ctx.respuesta = entrar(ctx, CLAVE)


@when("inicio sesión con una contraseña incorrecta")
def con_clave_mala(ctx):
    ctx.respuesta = entrar(ctx, CLAVE_MALA)


@when(parsers.parse('inicio sesión como "{email}" con mi contraseña'))
def con_otro_correo(ctx, email):
    ctx.respuesta = entrar(ctx, CLAVE, email=email)


@then("entro a mi cuenta")
def entro(ctx):
    assert ctx.respuesta.status_code == 200, ctx.respuesta.data
    assert "access" in ctx.respuesta.data


@then("no entro a mi cuenta")
def no_entro(ctx):
    assert ctx.respuesta.status_code == 401
    assert "access" not in ctx.respuesta.data


@then(parsers.parse('veo el mensaje "{mensaje}"'))
def veo_mensaje(ctx, mensaje):
    assert str(ctx.respuesta.data["detail"]) == mensaje


@then("veo que hay demasiados intentos")
def demasiados_intentos(ctx):
    assert ctx.respuesta.status_code == 429
    assert "Demasiados intentos" in str(ctx.respuesta.data["detail"])
