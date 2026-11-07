"""Pruebas de HU-67 · Pedidos del día por sede (SCRUM-88)."""
from datetime import datetime, time, timedelta

import pytest
from django.contrib.auth.models import Group
from django.utils import timezone
from rest_framework.test import APIClient

from pedidos.models import EstadoPedido as E
from pedidos.models import Pedido
from sedes.models import Ciudad, Sede
from usuarios.models import Empleado, Usuario
from usuarios.roles import ADMINISTRADOR, COCINA, OPERADOR, REPARTIDOR

pytestmark = pytest.mark.django_db

RESUMEN = "/api/pedidos/resumen-dia/"
CLAVE = "ClaveSegura2026"


# --- Datos de prueba ------------------------------------------------------------


@pytest.fixture
def ciudad():
    return Ciudad.objects.create(nombre="Cali")


def crear_sede(ciudad, nombre, activa=True):
    return Sede.objects.create(
        ciudad=ciudad, nombre=nombre, direccion="Calle 1 # 2-3", latitud=3.45,
        longitud=-76.53, barrio="Centro", telefono="3000000000",
        correo=f"{nombre.lower().replace(' ', '')}@correo.com", activa=activa,
    )


@pytest.fixture
def centro(ciudad):
    return crear_sede(ciudad, "Sede Centro")


@pytest.fixture
def sur(ciudad):
    return crear_sede(ciudad, "Sede Sur")


def crear_personal(rol, email, sede=None):
    usuario = Usuario.objects.create_user(username=email, email=email, password=CLAVE)
    usuario.groups.add(Group.objects.get_or_create(name=rol)[0])
    if sede is not None:
        Empleado.objects.create(
            usuario=usuario, sede=sede, tipo_documento="CC", num_documento=email[:10],
            nombres="Nombre", apellidos="Prueba", celular="3001234567", direccion="Calle 4",
        )
    return usuario


@pytest.fixture
def operador(centro):
    return crear_personal(OPERADOR, "operador@correo.com", centro)


@pytest.fixture
def admin():
    return crear_personal(ADMINISTRADOR, "admin@correo.com")


def a_las(dias, hora, minuto=0):
    """Momento local: hoy + `dias` a la hora indicada."""
    fecha = timezone.localdate() + timedelta(days=dias)
    return timezone.make_aware(datetime.combine(fecha, time(hora, minuto)))


_consecutivo = iter(range(1, 10_000))


def crear_pedido(sede, estado=E.RECIBIDO, cuando=None):
    pedido = Pedido.objects.create(sede=sede, numero_pedido=f"P-{next(_consecutivo)}", estado=estado)
    if cuando is not None:
        # fecha_creacion es auto_now_add: se cambia después de crear.
        Pedido.objects.filter(pk=pedido.pk).update(fecha_creacion=cuando)
    return pedido


def api_de(usuario=None):
    api = APIClient()
    if usuario is not None:
        api.force_authenticate(usuario)
    return api


def resumen_de(respuesta, sede):
    return next(s for s in respuesta.data["sedes"] if s["sede_id"] == sede.id)


# --- Criterio: resumen contador por estado del flujo ---------------------------


def test_cuenta_los_pedidos_de_hoy_por_estado(operador, centro):
    crear_pedido(centro, E.PENDIENTE_APROBACION)
    crear_pedido(centro, E.EN_PREPARACION)
    crear_pedido(centro, E.EN_PREPARACION)
    crear_pedido(centro, E.ENTREGADO)
    crear_pedido(centro, E.CANCELADO)

    respuesta = api_de(operador).get(RESUMEN)

    assert respuesta.status_code == 200
    assert respuesta.data["fecha"] == timezone.localdate()
    centro_hoy = resumen_de(respuesta, centro)
    assert centro_hoy["nombre"] == "Sede Centro"
    assert centro_hoy["total"] == 5
    assert centro_hoy["por_estado"][E.EN_PREPARACION] == 2
    assert centro_hoy["por_estado"][E.ENTREGADO] == 1
    assert centro_hoy["por_estado"][E.CANCELADO] == 1


def test_todos_los_estados_aparecen_aunque_esten_en_cero(operador, centro):
    centro_hoy = resumen_de(api_de(operador).get(RESUMEN), centro)

    assert set(centro_hoy["por_estado"]) == set(E.values)
    assert centro_hoy["total"] == 0
    assert all(cantidad == 0 for cantidad in centro_hoy["por_estado"].values())


# --- Criterio: solo pedidos del día actual (hora de Colombia) ------------------


def test_solo_cuenta_desde_la_medianoche_local(operador, centro):
    crear_pedido(centro, cuando=a_las(0, 0, 5))  # hoy 00:05
    crear_pedido(centro, cuando=a_las(0, 23, 55))  # hoy 23:55
    crear_pedido(centro, cuando=a_las(-1, 23, 55))  # ayer 23:55
    crear_pedido(centro, cuando=a_las(1, 0, 5))  # mañana 00:05

    assert resumen_de(api_de(operador).get(RESUMEN), centro)["total"] == 2


# --- Criterio: por sede ---------------------------------------------------------


def test_operador_solo_ve_su_sede(operador, centro, sur):
    crear_pedido(centro)
    crear_pedido(sur)
    crear_pedido(sur)

    respuesta = api_de(operador).get(RESUMEN)

    assert [s["sede_id"] for s in respuesta.data["sedes"]] == [centro.id]
    assert respuesta.data["sedes"][0]["total"] == 1


def test_operador_no_puede_ver_otra_sede_con_el_filtro(operador, centro, sur):
    crear_pedido(sur)

    respuesta = api_de(operador).get(RESUMEN, {"sede": sur.id})

    assert [s["sede_id"] for s in respuesta.data["sedes"]] == [centro.id]


def test_administrador_ve_todas_las_sedes_activas(admin, ciudad, centro, sur):
    cerrada = crear_sede(ciudad, "Sede Cerrada", activa=False)
    crear_pedido(centro)
    crear_pedido(sur)
    crear_pedido(sur)

    respuesta = api_de(admin).get(RESUMEN)

    assert [s["nombre"] for s in respuesta.data["sedes"]] == ["Sede Centro", "Sede Sur"]
    assert resumen_de(respuesta, sur)["total"] == 2
    assert cerrada.id not in [s["sede_id"] for s in respuesta.data["sedes"]]


def test_administrador_filtra_una_sede(admin, centro, sur):
    crear_pedido(sur)

    respuesta = api_de(admin).get(RESUMEN, {"sede": sur.id})

    assert [s["sede_id"] for s in respuesta.data["sedes"]] == [sur.id]


def test_filtro_de_sede_invalido_responde_400(admin):
    assert api_de(admin).get(RESUMEN, {"sede": "abc"}).status_code == 400


# --- Permisos -------------------------------------------------------------------


def test_sin_sesion_responde_401():
    assert api_de().get(RESUMEN).status_code == 401


@pytest.mark.parametrize("rol", [COCINA, REPARTIDOR])
def test_otros_roles_no_ven_el_resumen(centro, rol):
    usuario = crear_personal(rol, f"{rol}@correo.com", centro)

    assert api_de(usuario).get(RESUMEN).status_code == 403
