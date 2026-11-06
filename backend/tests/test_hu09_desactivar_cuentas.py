"""Pruebas de HU-09 · Desactivar cuentas (SCRUM-99)."""
import pytest
from django.contrib.auth.models import Group
from rest_framework.test import APIClient

from pedidos.models import Pedido
from sedes.models import Ciudad, Sede
from usuarios.models import Cliente, Empleado, Repartidor, Usuario
from usuarios.roles import ADMINISTRADOR, OPERADOR, REPARTIDOR

pytestmark = pytest.mark.django_db

CUENTAS = "/api/usuarios/cuentas/"
CLAVE = "ClaveSegura2026"


def url(usuario):
    return f"{CUENTAS}{usuario.id}/"


@pytest.fixture
def sede():
    ciudad = Ciudad.objects.create(nombre="Cali")
    return Sede.objects.create(
        ciudad=ciudad, nombre="Sede Centro", direccion="Calle 1 # 2-3", latitud=3.45,
        longitud=-76.53, barrio="Centro", telefono="3000000000", correo="centro@correo.com",
    )


def crear_personal(rol, email, sede=None, nombre="Nombre"):
    usuario = Usuario.objects.create_user(username=email, email=email, password=CLAVE)
    usuario.groups.add(Group.objects.get_or_create(name=rol)[0])
    if sede is not None:
        Empleado.objects.create(
            usuario=usuario, sede=sede, tipo_documento="CC", num_documento=email[:10],
            nombres=nombre, apellidos="Prueba", celular="3001234567", direccion="Calle 4",
        )
    return usuario


def crear_cliente(email="ana@correo.com", celular="3001112233"):
    usuario = Usuario.objects.create_user(username=email, email=email, password=CLAVE)
    Cliente.objects.create(
        usuario=usuario, tipo_documento="CC", num_documento=celular, nombres="Ana",
        apellidos="Pérez", celular=celular, fecha_nacimiento="2000-01-01",
    )
    return usuario


def api_de(usuario=None):
    api = APIClient()
    if usuario is not None:
        api.force_authenticate(usuario)
    return api


@pytest.fixture
def admin():
    return crear_personal(ADMINISTRADOR, "admin@correo.com")


def desactivar(admin, usuario):
    return api_de(admin).patch(url(usuario), {"activa": False}, format="json")


# --- Criterio 1: la cuenta queda inactiva y no puede iniciar sesión ----------------


def test_admin_desactiva_un_cliente_y_ya_no_inicia_sesion(admin):
    cliente = crear_cliente()

    respuesta = desactivar(admin, cliente)

    assert respuesta.status_code == 200
    assert respuesta.data["activa"] is False
    cliente.refresh_from_db()
    assert cliente.is_active is False
    login = APIClient().post(
        "/api/usuarios/login/", {"email": "ana@correo.com", "password": CLAVE}, format="json"
    )
    assert login.status_code == 401


def test_admin_desactiva_un_empleado_y_ya_no_inicia_sesion(admin, sede):
    operador = crear_personal(OPERADOR, "operador@correo.com", sede)

    assert desactivar(admin, operador).status_code == 200
    login = APIClient().post(
        "/api/usuarios/login-personal/", {"email": "operador@correo.com", "password": CLAVE}, format="json"
    )
    assert login.status_code == 401


def test_repartidor_desactivado_queda_no_disponible(admin, sede):
    usuario = crear_personal(REPARTIDOR, "repa@correo.com", sede)
    perfil = Repartidor.objects.create(empleado=usuario.empleado, disponible=True)

    desactivar(admin, usuario)

    perfil.refresh_from_db()
    assert perfil.disponible is False


# --- Criterio 2: una sesión abierta deja de valer en la siguiente acción -------------


def test_sesion_abierta_deja_de_valer(admin):
    crear_cliente()
    api = APIClient()
    tokens = api.post(
        "/api/usuarios/login/", {"email": "ana@correo.com", "password": CLAVE}, format="json"
    ).data
    api.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")
    assert api.get("/api/usuarios/direcciones/").status_code == 200

    desactivar(admin, Usuario.objects.get(email="ana@correo.com"))

    assert api.get("/api/usuarios/direcciones/").status_code == 401
    renovar = APIClient().post("/api/auth/token/refresh/", {"refresh": tokens["refresh"]}, format="json")
    assert renovar.status_code == 401


# --- Criterio 3: los datos y pedidos se conservan ------------------------------------


def test_desactivar_conserva_datos_y_pedidos(admin, sede):
    cliente = crear_cliente()
    pedido = Pedido.objects.create(sede=sede, numero_pedido="P-1", cliente=cliente.cliente)

    desactivar(admin, cliente)

    assert Cliente.objects.filter(usuario=cliente).exists()
    assert Pedido.objects.filter(pk=pedido.pk, cliente=cliente.cliente).exists()
    assert api_de(admin).get(url(cliente)).data["nombre"] == "Ana Pérez"


# --- Criterio 4: el administrador no puede desactivarse a sí mismo -----------------


def test_admin_no_puede_desactivarse_a_si_mismo(admin):
    respuesta = desactivar(admin, admin)

    assert respuesta.status_code == 400
    assert "activa" in respuesta.data
    admin.refresh_from_db()
    assert admin.is_active is True


# --- Reactivar (adelanta HU-80) -----------------------------------------------------


def test_admin_reactiva_una_cuenta(admin):
    cliente = crear_cliente()
    desactivar(admin, cliente)

    respuesta = api_de(admin).patch(url(cliente), {"activa": True}, format="json")

    assert respuesta.status_code == 200
    login = APIClient().post(
        "/api/usuarios/login/", {"email": "ana@correo.com", "password": CLAVE}, format="json"
    )
    assert login.status_code == 200


def test_activa_es_obligatorio(admin):
    cliente = crear_cliente()

    assert api_de(admin).patch(url(cliente), {}, format="json").status_code == 400
    assert api_de(admin).patch(url(cliente), {"activa": "tal vez"}, format="json").status_code == 400


def test_el_correo_no_se_modifica(admin):
    cliente = crear_cliente()

    api_de(admin).patch(url(cliente), {"activa": True, "email": "otro@correo.com"}, format="json")

    cliente.refresh_from_db()
    assert cliente.email == "ana@correo.com"


# --- Listado para la tabla del administrador -----------------------------------------


def test_listado_muestra_clientes_y_personal(admin, sede):
    crear_cliente()
    crear_personal(OPERADOR, "operador@correo.com", sede, nombre="Olga")

    datos = {c["email"]: c for c in api_de(admin).get(CUENTAS).data}

    assert datos["ana@correo.com"]["tipo"] == "cliente"
    assert datos["operador@correo.com"]["tipo"] == "personal"
    assert datos["operador@correo.com"]["rol"] == OPERADOR
    assert datos["operador@correo.com"]["sede"] == "Sede Centro"
    assert datos["admin@correo.com"]["es_usted"] is True


def test_listado_filtra_por_tipo_estado_y_busqueda(admin, sede):
    crear_cliente()
    beto = crear_cliente("beto@correo.com", "3004445566")
    crear_personal(OPERADOR, "operador@correo.com", sede)
    desactivar(admin, beto)
    api = api_de(admin)

    assert [c["email"] for c in api.get(CUENTAS, {"tipo": "cliente"}).data] == [
        "ana@correo.com",
        "beto@correo.com",
    ]
    assert "ana@correo.com" not in [c["email"] for c in api.get(CUENTAS, {"tipo": "personal"}).data]
    assert [c["email"] for c in api.get(CUENTAS, {"activa": "false"}).data] == ["beto@correo.com"]
    assert [c["email"] for c in api.get(CUENTAS, {"buscar": "PÉREZ"}).data] == [
        "ana@correo.com",
        "beto@correo.com",
    ]


def test_reconoce_empleados_con_rol_en_mayusculas(admin, sede):
    """Los empleados creados por HU-08 quedan en grupos en mayúsculas (p. ej. "COCINA")."""
    crear_personal("COCINA", "cocina@correo.com", sede)

    datos = {c["email"]: c for c in api_de(admin).get(CUENTAS).data}

    assert datos["cocina@correo.com"]["rol"] == "cocina"
    assert datos["cocina@correo.com"]["tipo"] == "personal"


# --- Permisos ----------------------------------------------------------------------


def test_sin_sesion_responde_401():
    assert api_de().get(CUENTAS).status_code == 401


def test_solo_el_administrador_gestiona_cuentas(sede):
    operador = crear_personal(OPERADOR, "operador@correo.com", sede)
    cliente = crear_cliente()
    api = api_de(operador)

    assert api.get(CUENTAS).status_code == 403
    assert api.patch(url(cliente), {"activa": False}, format="json").status_code == 403
    cliente.refresh_from_db()
    assert cliente.is_active is True


def test_cuenta_inexistente_responde_404(admin):
    assert api_de(admin).patch(f"{CUENTAS}9999/", {"activa": False}, format="json").status_code == 404
