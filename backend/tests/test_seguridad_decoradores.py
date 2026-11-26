"""
Seguridad · Decoradores de Django en las vistas delicadas (Clase 10, diapositiva 38).

- sensitive_post_parameters("password"): si una petición termina en error 500, el
  reporte de Django (correo a los admins, página de depuración) oculta la contraseña.
- never_cache: las respuestas con datos personales o de dinero llevan
  `Cache-Control: no-store`, así ni el navegador ni un proxy las guardan.
"""
from datetime import date

import pytest
from django.contrib.auth.models import Group
from django.views.debug import SafeExceptionReporterFilter
from rest_framework.test import APIClient, APIRequestFactory

from usuarios.contrasena import RestablecerContrasenaView
from usuarios.models import Cliente, Usuario
from usuarios.roles import ADMINISTRADOR
from usuarios.views import EmpleadoManagementView, LoginPersonalView, LoginView, RegistroClienteView

pytestmark = pytest.mark.django_db

CLAVE = "ClaveSegura2026"


# --- sensitive_post_parameters --------------------------------------------------------


@pytest.mark.parametrize(
    "vista", [LoginView, LoginPersonalView, RegistroClienteView, RestablecerContrasenaView, EmpleadoManagementView]
)
def test_la_contrasena_no_sale_en_el_reporte_de_errores(vista):
    request = APIRequestFactory().post("/x/", {"email": "a@correo.com", "password": CLAVE})
    vista.as_view()(request)

    assert request.sensitive_post_parameters == ("password",)
    parametros = SafeExceptionReporterFilter().get_post_parameters(request)
    assert parametros["password"] != CLAVE
    assert set(parametros["password"]) == {"*"}
    assert parametros["email"] == "a@correo.com"  # lo demás sí aparece, para depurar


# --- never_cache ---------------------------------------------------------------------------


def con_sesion(usuario):
    api = APIClient()
    api.force_authenticate(usuario)
    return api


@pytest.fixture
def cliente():
    usuario = Usuario.objects.create_user(username="ana@correo.com", email="ana@correo.com", password=CLAVE)
    Cliente.objects.create(
        usuario=usuario, tipo_documento="CC", num_documento="123", nombres="Ana",
        apellidos="Gómez", celular="3001234567", fecha_nacimiento=date(2000, 1, 1),
    )
    return usuario


@pytest.fixture
def admin():
    usuario = Usuario.objects.create_user(username="admin@correo.com", email="admin@correo.com", password=CLAVE)
    usuario.groups.add(Group.objects.get_or_create(name=ADMINISTRADOR)[0])
    return usuario


def sin_cache(respuesta):
    cabecera = respuesta.headers.get("Cache-Control", "")
    return "no-store" in cabecera and "no-cache" in cabecera and "private" in cabecera


@pytest.mark.parametrize("url", ["/api/usuarios/perfil/", "/api/pedidos/mios/", "/api/usuarios/carrito/"])
def test_datos_del_cliente_no_se_guardan_en_cache(cliente, url):
    respuesta = con_sesion(cliente).get(url)

    assert respuesta.status_code == 200
    assert sin_cache(respuesta)


@pytest.mark.parametrize(
    "url",
    [
        "/api/pedidos/reportes/ventas/",
        "/api/pedidos/reportes/tiempos/",
        "/api/pedidos/reportes/demanda/",
        "/api/pedidos/resumen-dia/",
        "/api/pedidos/indicadores/",
        "/api/usuarios/empleados/",
    ],
)
def test_reportes_del_admin_no_se_guardan_en_cache(admin, url):
    respuesta = con_sesion(admin).get(url)

    assert respuesta.status_code == 200
    assert sin_cache(respuesta)


@pytest.mark.parametrize("url", ["/api/pedidos/confirmar/", "/api/pedidos/operador/crear/"])
def test_crear_pedido_no_se_guarda_en_cache_ni_siquiera_si_falla(cliente, url):
    # Cuerpo vacío: 400 o 403 según el rol, pero la cabecera va en cualquier respuesta.
    respuesta = con_sesion(cliente).post(url, {}, format="json")

    assert respuesta.status_code in (400, 403)
    assert sin_cache(respuesta)


def test_el_perfil_del_personal_no_se_guarda_en_cache(admin):
    respuesta = con_sesion(admin).get("/api/usuarios/perfil-personal/")

    assert respuesta.status_code == 200
    assert sin_cache(respuesta)


def test_el_menu_publico_no_lleva_no_store():
    """Solo las vistas delicadas: el menú se puede guardar en caché sin problema."""
    respuesta = APIClient().get("/api/menu/sedes/")

    assert respuesta.status_code == 200
    assert "no-store" not in respuesta.headers.get("Cache-Control", "")
