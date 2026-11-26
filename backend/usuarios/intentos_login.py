"""
Protección del login contra fuerza bruta (Clase 10, diapositivas 19 y 43).

Hay dos barreras que se complementan:

1. Por IP: `ProtegidaContraFuerzaBruta` aplica `ScopedRateThrottle` con el alcance
   "login" (LOGIN_RATE_LIMIT, 5 por minuto). Frena a quien prueba muchas
   contraseñas desde la misma máquina.
2. Por cuenta: tras LOGIN_FAILS_LIMIT contraseñas malas para un mismo correo, ese
   correo queda bloqueado LOGIN_FAILS_TIMEOUT segundos aunque el atacante cambie
   de IP. Un login exitoso borra el contador.

Los contadores viven en el caché de Django (Redis en producción). Cada fallo y
cada bloqueo se registran en el log con el correo y la IP, nunca con la contraseña.
"""
import logging

from django.conf import settings
from django.core.cache import cache
from rest_framework.exceptions import Throttled
from rest_framework.throttling import BaseThrottle, ScopedRateThrottle

logger = logging.getLogger(__name__)

MENSAJE_DEMASIADOS_INTENTOS = "Demasiados intentos. Espera unos minutos e inténtalo de nuevo."


class DemasiadosIntentos(Throttled):
    """429 con el mensaje en español (el de DRF dice "Request was throttled")."""

    default_detail = MENSAJE_DEMASIADOS_INTENTOS
    extra_detail_singular = "Podrás intentarlo en {wait} segundo."
    extra_detail_plural = "Podrás intentarlo en {wait} segundos."


class ProtegidaContraFuerzaBruta:
    """Mixin para las vistas públicas de login y restablecimiento: límite por IP."""

    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "login"

    def throttled(self, request, wait):
        raise DemasiadosIntentos(wait=wait)


def _clave(email):
    # El correo se compara sin mayúsculas, igual que en LoginSerializer (email__iexact).
    return f"login-fallos:{(email or '').strip().lower()}"


def ip_de(request):
    """IP del cliente, la misma que usa el límite de DRF (tiene en cuenta X-Forwarded-For)."""
    return BaseThrottle().get_ident(request) if request is not None else "desconocida"


def esta_bloqueado(email):
    return cache.get(_clave(email), 0) >= settings.LOGIN_FAILS_LIMIT


def verificar_bloqueo(email, request):
    """Lanza 429 si el correo está bloqueado. Se llama antes de revisar la contraseña."""
    if esta_bloqueado(email):
        logger.warning("Login rechazado: cuenta bloqueada por intentos fallidos (correo=%s, ip=%s)",
                       email, ip_de(request))
        raise DemasiadosIntentos(wait=settings.LOGIN_FAILS_TIMEOUT)


def registrar_fallo(email, request):
    """Suma un fallo al correo. Al llegar al límite, el bloqueo dura LOGIN_FAILS_TIMEOUT desde ahí."""
    clave = _clave(email)
    # add() solo crea la clave si no existe; incr() conserva su vencimiento.
    cache.add(clave, 0, timeout=settings.LOGIN_FAILS_TIMEOUT)
    try:
        fallos = cache.incr(clave)
    except ValueError:  # la clave venció justo entre add() e incr()
        cache.set(clave, 1, timeout=settings.LOGIN_FAILS_TIMEOUT)
        fallos = 1

    ip = ip_de(request)
    if fallos >= settings.LOGIN_FAILS_LIMIT:
        cache.touch(clave, settings.LOGIN_FAILS_TIMEOUT)
        logger.warning("Cuenta bloqueada %s s tras %s intentos fallidos (correo=%s, ip=%s)",
                       settings.LOGIN_FAILS_TIMEOUT, fallos, email, ip)
    else:
        logger.warning("Intento de login fallido %s/%s (correo=%s, ip=%s)",
                       fallos, settings.LOGIN_FAILS_LIMIT, email, ip)


def limpiar_fallos(email):
    cache.delete(_clave(email))
