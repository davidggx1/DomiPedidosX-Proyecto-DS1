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
