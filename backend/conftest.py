import pytest
from django.core.cache import cache


@pytest.fixture(autouse=True)
def cache_limpio():
    """
    El límite de peticiones del login y el contador de intentos fallidos viven en
    el caché (docs/seguridad.md). Se vacía antes de cada prueba para que los
    intentos de una no cuenten en la siguiente.
    """
    cache.clear()
    yield
    cache.clear()


@pytest.fixture(autouse=True)
def sin_redireccion_https(settings):
    """
    El CI corre con DJANGO_DEBUG=False, que activa SECURE_SSL_REDIRECT: el cliente de
    pruebas usa http y todas las respuestas serían 301. Las pruebas que revisan la
    redirección la vuelven a activar (tests/test_seguridad_produccion.py).
    """
    settings.SECURE_SSL_REDIRECT = False
