"""Pruebas de HU-41 · Disponibilidad del repartidor (SCRUM-74)."""
import pytest
from django.contrib.auth.models import Group
from rest_framework.test import APIClient

from pedidos.models import EstadoPedido, Pedido
from sedes.models import Ciudad, Sede
from usuarios.models import Empleado, Repartidor, Usuario
from usuarios.roles import ADMINISTRADOR, COCINA, OPERADOR, REPARTIDOR

pytestmark = pytest.mark.django_db

MI_DISPONIBILIDAD = "/api/usuarios/repartidor/disponibilidad/"
REPARTIDORES = "/api/usuarios/repartidores/"
LOGIN_PERSONAL = "/api/usuarios/login-personal/"
CLAVE = "ClaveSegura2026"


@pytest.fixture
def ciudad():
    return Ciudad.objects.create(nombre="Cali")


def crear_sede(ciudad, nombre):
    return Sede.objects.create(
        ciudad=ciudad, nombre=nombre, direccion="Calle 1 # 2-3", latitud=3.45,
        longitud=-76.53, barrio="Centro", telefono="3000000000",
        correo=f"{nombre.lower().replace(' ', '')}@correo.com",
    )


@pytest.fixture
def centro(ciudad):
    return crear_sede(ciudad, "Sede Centro")


@pytest.fixture
def sur(ciudad):
    return crear_sede(ciudad, "Sede Sur")


def crear_personal(rol, email, sede=None, activo=True):
    usuario = Usuario.objects.create_user(
        username=email, email=email, password=CLAVE, is_active=activo
    )
    usuario.groups.add(Group.objects.get_or_create(name=rol)[0])
    empleado = None
    if sede is not None:
        empleado = Empleado.objects.create(
            usuario=usuario, sede=sede, tipo_documento="CC", num_documento=email[:10],
            nombres=email.split("@")[0].capitalize(), apellidos="Prueba",
            celular="3001234567", direccion="Calle 4",
        )
    return usuario, empleado


def crear_repartidor(email, sede, disponible=False, activo=True):
    usuario, empleado = crear_personal(REPARTIDOR, email, sede, activo)
    perfil = Repartidor.objects.create(empleado=empleado, disponible=disponible)
    return usuario, perfil


def api_de(usuario=None):
    api = APIClient()
    if usuario is not None:
        api.force_authenticate(usuario)
    return api


# --- Criterio 4: al iniciar sesión arranca "No disponible" ----------------------


def test_repartidor_nuevo_arranca_no_disponible(centro):
    _, empleado = crear_personal(REPARTIDOR, "nuevo@correo.com", centro)
    repartidor = Repartidor.objects.create(empleado=empleado)

    assert repartidor.disponible is False


def test_al_iniciar_sesion_queda_no_disponible(centro):
    _, perfil = crear_repartidor("ana@correo.com", centro, disponible=True)

    respuesta = APIClient().post(
        LOGIN_PERSONAL, {"email": "ana@correo.com", "password": CLAVE}, format="json"
    )

    assert respuesta.status_code == 200
    perfil.refresh_from_db()
    assert perfil.disponible is False


def test_registro_de_repartidor_por_el_administrador_arranca_no_disponible(centro):
    admin, _ = crear_personal(ADMINISTRADOR, "admin@correo.com")
    admin.is_staff = True
    admin.save()

    respuesta = api_de(admin).post(
        "/api/usuarios/empleados/",
        {
            "email": "repa@correo.com", "nombres": "Repa", "apellidos": "Nuevo",
            "tipo_documento": "CC", "num_documento": "1234567890", "celular": "3001112233",
            "direccion": "Calle 9", "rol": "REPARTIDOR", "sede_id": centro.id,
        },
        format="json",
    )

    assert respuesta.status_code == 201
    assert Repartidor.objects.get(empleado__usuario__email="repa@correo.com").disponible is False


# --- Criterio 1: el repartidor cambia su estado y el operador lo ve -------------


def test_repartidor_consulta_su_disponibilidad(centro):
    usuario, _ = crear_repartidor("ana@correo.com", centro)

    respuesta = api_de(usuario).get(MI_DISPONIBILIDAD)

    assert respuesta.status_code == 200
    assert respuesta.data == {"disponible": False}


def test_repartidor_activa_y_desactiva_su_jornada(centro):
    usuario, perfil = crear_repartidor("ana@correo.com", centro)
    api = api_de(usuario)

    assert api.patch(MI_DISPONIBILIDAD, {"disponible": True}, format="json").status_code == 200
    perfil.refresh_from_db()
    assert perfil.disponible is True

    assert api.patch(MI_DISPONIBILIDAD, {"disponible": False}, format="json").status_code == 200
    perfil.refresh_from_db()
    assert perfil.disponible is False


def test_disponible_es_obligatorio_y_booleano(centro):
    usuario, _ = crear_repartidor("ana@correo.com", centro)
    api = api_de(usuario)

    assert api.patch(MI_DISPONIBILIDAD, {}, format="json").status_code == 400
    assert api.patch(MI_DISPONIBILIDAD, {"disponible": "tal vez"}, format="json").status_code == 400


def test_el_operador_ve_el_cambio_en_su_panel(centro):
    repartidor, _ = crear_repartidor("ana@correo.com", centro)
    operador, _ = crear_personal(OPERADOR, "operador@correo.com", centro)

    api_de(repartidor).patch(MI_DISPONIBILIDAD, {"disponible": True}, format="json")
    respuesta = api_de(operador).get(REPARTIDORES)

    assert respuesta.status_code == 200
    assert [(r["nombres"], r["disponible"]) for r in respuesta.data] == [("Ana", True)]


def test_operador_solo_ve_repartidores_de_su_sede(centro, sur):
    crear_repartidor("ana@correo.com", centro)
    crear_repartidor("beto@correo.com", sur)
    operador, _ = crear_personal(OPERADOR, "operador@correo.com", centro)

    respuesta = api_de(operador).get(REPARTIDORES)

    assert [r["nombres"] for r in respuesta.data] == ["Ana"]


def test_administrador_ve_todos_y_filtra_por_disponibles(centro, sur):
    crear_repartidor("ana@correo.com", centro, disponible=True)
    crear_repartidor("beto@correo.com", sur)
    admin, _ = crear_personal(ADMINISTRADOR, "admin@correo.com")
    api = api_de(admin)

    assert [r["nombres"] for r in api.get(REPARTIDORES).data] == ["Ana", "Beto"]
    disponibles = api.get(REPARTIDORES, {"disponible": "true"}).data
    assert [r["nombres"] for r in disponibles] == ["Ana"]


def test_repartidores_con_cuenta_desactivada_no_aparecen(centro):
    crear_repartidor("ana@correo.com", centro, activo=False)
    operador, _ = crear_personal(OPERADOR, "operador@correo.com", centro)

    assert api_de(operador).get(REPARTIDORES).data == []


# --- Criterio 3: no disponible conserva sus entregas pendientes --------------------


def test_pasar_a_no_disponible_conserva_pedidos_asignados(centro):
    usuario, perfil = crear_repartidor("ana@correo.com", centro, disponible=True)
    pedido = Pedido.objects.create(
        sede=centro, numero_pedido="P-41", repartidor=perfil, estado=EstadoPedido.EN_CAMINO
    )
    operador, _ = crear_personal(OPERADOR, "operador@correo.com", centro)

    api_de(usuario).patch(MI_DISPONIBILIDAD, {"disponible": False}, format="json")

    pedido.refresh_from_db()
    assert pedido.repartidor_id == perfil.id
    assert pedido.estado == EstadoPedido.EN_CAMINO
    datos = api_de(operador).get(REPARTIDORES).data[0]
    assert datos["disponible"] is False
    assert datos["pedidos_activos"] == 1


# --- Permisos ----------------------------------------------------------------------


def test_sin_sesion_responde_401():
    assert api_de().get(MI_DISPONIBILIDAD).status_code == 401
    assert api_de().get(REPARTIDORES).status_code == 401


@pytest.mark.parametrize("rol", [OPERADOR, COCINA, ADMINISTRADOR])
def test_solo_el_repartidor_cambia_su_disponibilidad(centro, rol):
    usuario, _ = crear_personal(rol, f"{rol}@correo.com", centro)

    assert api_de(usuario).patch(MI_DISPONIBILIDAD, {"disponible": True}, format="json").status_code == 403


@pytest.mark.parametrize("rol", [COCINA, REPARTIDOR])
def test_cocina_y_repartidor_no_ven_la_lista(centro, rol):
    usuario, _ = crear_personal(rol, f"{rol}@correo.com", centro)

    assert api_de(usuario).get(REPARTIDORES).status_code == 403


def test_repartidor_sin_perfil_responde_404(centro):
    usuario, _ = crear_personal(REPARTIDOR, "sinperfil@correo.com", centro)

    assert api_de(usuario).get(MI_DISPONIBILIDAD).status_code == 404
