"""
Seguridad · Configuración de producción (Clase 10, checklists de las diapositivas 44-47).

La configuración de producción se arma al importar settings.py con DJANGO_DEBUG=False,
así que se revisa en un proceso aparte. La redirección a https se prueba activándola.
"""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from rest_framework.test import APIClient

BACKEND = Path(__file__).resolve().parent.parent

pytestmark = pytest.mark.django_db


def settings_con(debug):
    """Valores de settings.py tal como quedan con DJANGO_DEBUG=<debug>."""
    codigo = (
        "import json; from config import settings as s; print(json.dumps({n: getattr(s, n, None) for n in ["
        "'SECURE_HSTS_SECONDS', 'SECURE_HSTS_INCLUDE_SUBDOMAINS', 'SECURE_CONTENT_TYPE_NOSNIFF',"
        "'X_FRAME_OPTIONS', 'SECURE_REFERRER_POLICY', 'SECURE_SSL_REDIRECT', 'SECURE_REDIRECT_EXEMPT',"
        "'DATA_UPLOAD_MAX_MEMORY_SIZE', 'FILE_UPLOAD_MAX_MEMORY_SIZE', 'FILE_UPLOAD_PERMISSIONS']}))"
    )
    entorno = {**os.environ, "DJANGO_DEBUG": str(debug)}
    entorno.pop("SECURE_HSTS_SECONDS", None)
    salida = subprocess.run(
        [sys.executable, "-c", codigo], cwd=BACKEND, env=entorno, capture_output=True, text=True, check=True
    )
    return json.loads(salida.stdout)


def test_produccion_activa_las_cabeceras_de_seguridad():
    valores = settings_con(debug=False)

    assert valores["SECURE_HSTS_SECONDS"] == 31536000  # 1 año
    assert valores["SECURE_HSTS_INCLUDE_SUBDOMAINS"] is True
    assert valores["SECURE_CONTENT_TYPE_NOSNIFF"] is True
    assert valores["X_FRAME_OPTIONS"] == "DENY"
    assert valores["SECURE_REFERRER_POLICY"] == "same-origin"
    assert valores["SECURE_SSL_REDIRECT"] is True
    assert valores["SECURE_REDIRECT_EXEMPT"] == [r"^api/docs/$"]


def test_desarrollo_no_redirige_a_https():
    assert not settings_con(debug=True)["SECURE_SSL_REDIRECT"]


def test_limites_de_carga_en_cualquier_entorno():
    for debug in (True, False):
        valores = settings_con(debug)
        assert valores["DATA_UPLOAD_MAX_MEMORY_SIZE"] == 5 * 1024 * 1024
        assert valores["FILE_UPLOAD_MAX_MEMORY_SIZE"] == 5 * 1024 * 1024
        assert valores["FILE_UPLOAD_PERMISSIONS"] == 0o644


def test_http_redirige_a_https_salvo_el_health_check(settings):
    settings.SECURE_SSL_REDIRECT = True
    settings.SECURE_REDIRECT_EXEMPT = [r"^api/docs/$"]
    settings.SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    cliente = APIClient()

    respuesta = cliente.get("/api/menu/sedes/")
    assert respuesta.status_code == 301
    assert respuesta["Location"].startswith("https://")

    # Render revisa /api/docs/ por http interno: debe responder 200, no 301.
    assert cliente.get("/api/docs/").status_code == 200
    # Detrás del proxy de Render, una petición que llegó por https no se redirige.
    assert cliente.get("/api/menu/sedes/", HTTP_X_FORWARDED_PROTO="https").status_code != 301


def test_las_respuestas_llevan_nosniff_y_deny(settings):
    settings.SECURE_CONTENT_TYPE_NOSNIFF = True
    settings.X_FRAME_OPTIONS = "DENY"
    settings.SECURE_REFERRER_POLICY = "same-origin"

    respuesta = APIClient().get("/api/menu/sedes/")

    assert respuesta["X-Content-Type-Options"] == "nosniff"
    assert respuesta["X-Frame-Options"] == "DENY"
    assert respuesta["Referrer-Policy"] == "same-origin"


def test_cuerpo_de_mas_de_5_mb_se_rechaza():
    grande = json.dumps({"email": "a" * (5 * 1024 * 1024 + 1)})

    respuesta = APIClient().post("/api/usuarios/registro/", grande, content_type="application/json")

    assert respuesta.status_code == 400
