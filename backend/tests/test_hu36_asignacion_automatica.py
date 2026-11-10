"""Pruebas de HU-36 · Asignación automática de repartidor (SCRUM-114)."""
from datetime import timedelta

import pytest
from django.contrib.auth.models import Group
from django.test import override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from pedidos.asignacion import asignar, retirar
from pedidos.asignacion_automatica import asignar_automaticamente, candidatos
from pedidos.estados import cambiar_estado
from pedidos.models import EstadoPedido as E
from pedidos.models import HistorialEstadoPedido, OrigenPedido, Pedido
from sedes.models import Ciudad, Sede
from usuarios.models import Empleado, Repartidor, Usuario
from usuarios.roles import COCINA, OPERADOR, REPARTIDOR

pytestmark = pytest.mark.django_db

DESPACHO = "/api/pedidos/despacho/"
CLAVE = "ClaveSegura2026"


# --- Datos de prueba ------------------------------------------------------------


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


def crear_personal(rol, email, sede, activo=True, nombre="Nombre"):
    usuario = Usuario.objects.create_user(username=email, email=email, password=CLAVE, is_active=activo)
    usuario.groups.add(Group.objects.get_or_create(name=rol)[0])
    empleado = Empleado.objects.create(
        usuario=usuario, sede=sede, tipo_documento="CC", num_documento=email[:10],
        nombres=nombre, apellidos="Prueba", celular="3001234567", direccion="Calle 4",
    )
    return usuario, empleado


def crear_repartidor(email, sede, disponible=True, activo=True):
    _, empleado = crear_personal(REPARTIDOR, email, sede, activo, nombre=email.split("@")[0])
    return Repartidor.objects.create(empleado=empleado, disponible=disponible)


def crear_pedido(sede, numero="P-1", estado=E.LISTO_DESPACHO, **extra):
    return Pedido.objects.create(sede=sede, numero_pedido=numero, estado=estado, **extra)


def entrego_hace(repartidor, minutos, numero):
    """Deja en el historial una entrega terminada hace `minutos` minutos."""
    pedido = crear_pedido(repartidor.empleado.sede, numero, E.ENTREGADO, repartidor=repartidor)
    registro = HistorialEstadoPedido.objects.create(pedido=pedido, estado=E.ENTREGADO)
    HistorialEstadoPedido.objects.filter(pk=registro.pk).update(
        fecha_hora=timezone.now() - timedelta(minutes=minutos)
    )


@pytest.fixture
def cocinero(centro):
    return crear_personal(COCINA, "cocina@correo.com", centro)[0]


def pasar_a_listo(pedido, cocinero, capturar):
    """Cocina marca el pedido listo; se ejecutan los avisos que corren al confirmar."""
    with capturar(execute=True):
        cambiar_estado(pedido, E.LISTO_DESPACHO, cocinero, COCINA)
    pedido.refresh_from_db()
    return pedido


# --- Criterio 1: al quedar listo se asigna solo --------------------------------


def test_al_pasar_a_listo_se_asigna_un_repartidor_libre(
    centro, cocinero, django_capture_on_commit_callbacks
):
    ana = crear_repartidor("ana@correo.com", centro)
    pedido = crear_pedido(centro, estado=E.EN_PREPARACION)

    pedido = pasar_a_listo(pedido, cocinero, django_capture_on_commit_callbacks)

    assert pedido.repartidor == ana
    assert pedido.asignacion_automatica is True


def test_prefiere_al_que_tiene_menos_entregas_activas(centro):
    ocupada = crear_repartidor("ocupada@correo.com", centro)
    libre = crear_repartidor("libre@correo.com", centro)
    crear_pedido(centro, "P-EN-CURSO", E.EN_CAMINO, repartidor=ocupada)

    orden = list(candidatos(centro.id))

    assert orden[0] == libre
    assert orden[0].entregas_activas == 0


def test_no_asigna_repartidores_no_disponibles_inactivos_ni_de_otra_sede(centro, sur):
    crear_repartidor("nodisp@correo.com", centro, disponible=False)
    crear_repartidor("inactivo@correo.com", centro, activo=False)
    crear_repartidor("sur@correo.com", sur)
    pedido = crear_pedido(centro)

    assert asignar_automaticamente(pedido) is None
    pedido.refresh_from_db()
    assert pedido.repartidor is None


def test_salta_al_repartidor_ocupado_y_toma_el_siguiente(centro):
    ocupado = crear_repartidor("ocupado@correo.com", centro)
    libre = crear_repartidor("libre@correo.com", centro)
    crear_pedido(centro, "P-EN-CURSO", E.EN_CAMINO, repartidor=ocupado)
    pedido = crear_pedido(centro, "P-NUEVO")

    assert asignar_automaticamente(pedido) == libre


# --- Criterio 2: sin repartidores libres queda "Sin asignar" ------------------


def test_sin_repartidores_libres_el_pedido_queda_sin_asignar(
    centro, cocinero, django_capture_on_commit_callbacks
):
    ocupado = crear_repartidor("ocupado@correo.com", centro)
    crear_pedido(centro, "P-EN-CURSO", E.EN_CAMINO, repartidor=ocupado)
    pedido = crear_pedido(centro, "P-NUEVO", E.EN_PREPARACION)

    pedido = pasar_a_listo(pedido, cocinero, django_capture_on_commit_callbacks)

    assert pedido.estado == E.LISTO_DESPACHO  # el cambio de cocina no se pierde
    assert pedido.repartidor is None


def test_pedido_sin_asignar_aparece_en_despacho_para_el_operador(centro):
    operador, _ = crear_personal(OPERADOR, "operador@correo.com", centro)
    crear_pedido(centro, "P-SIN")
    api = APIClient()
    api.force_authenticate(operador)

    datos = api.get(DESPACHO).data

    assert datos[0]["repartidor"] is None
    assert datos[0]["asignacion_automatica"] is False


def test_pedidos_de_mostrador_no_se_asignan(centro):
    crear_repartidor("ana@correo.com", centro)
    pedido = crear_pedido(centro, origen=OrigenPedido.MOSTRADOR)

    assert asignar_automaticamente(pedido) is None


# --- Criterio 3: queda etiquetada como automática -----------------------------


def test_despacho_muestra_si_la_asignacion_fue_automatica(centro):
    operador, _ = crear_personal(OPERADOR, "operador@correo.com", centro)
    crear_repartidor("ana@correo.com", centro)
    asignar_automaticamente(crear_pedido(centro))
    api = APIClient()
    api.force_authenticate(operador)

    assert api.get(DESPACHO).data[0]["asignacion_automatica"] is True


def test_asignacion_manual_queda_marcada_como_manual(centro):
    ana = crear_repartidor("ana@correo.com", centro)
    pedido = asignar(crear_pedido(centro), ana)

    assert pedido.asignacion_automatica is False


def test_al_retirar_una_automatica_se_borra_la_etiqueta(centro):
    crear_repartidor("ana@correo.com", centro)
    pedido = crear_pedido(centro)
    asignar_automaticamente(pedido)

    pedido = retirar(pedido)

    assert pedido.repartidor is None
    assert pedido.asignacion_automatica is False


# --- Criterio 4: desempate por mayor tiempo de espera -------------------------


def test_empate_gana_quien_lleva_mas_tiempo_sin_entregar(centro):
    reciente = crear_repartidor("reciente@correo.com", centro)
    antiguo = crear_repartidor("antiguo@correo.com", centro)
    entrego_hace(reciente, 5, "H-1")
    entrego_hace(antiguo, 90, "H-2")

    assert asignar_automaticamente(crear_pedido(centro, "P-NUEVO")) == antiguo


def test_empate_va_primero_quien_nunca_ha_entregado(centro):
    veterano = crear_repartidor("veterano@correo.com", centro)
    nuevo = crear_repartidor("nuevo@correo.com", centro)
    entrego_hace(veterano, 300, "H-1")

    assert asignar_automaticamente(crear_pedido(centro, "P-NUEVO")) == nuevo


# --- Interruptor general --------------------------------------------------------


@override_settings(ASIGNACION_AUTOMATICA_REPARTIDOR=False)
def test_se_puede_apagar_desde_settings(centro, cocinero, django_capture_on_commit_callbacks):
    crear_repartidor("ana@correo.com", centro)
    pedido = crear_pedido(centro, estado=E.EN_PREPARACION)

    pedido = pasar_a_listo(pedido, cocinero, django_capture_on_commit_callbacks)

    assert pedido.repartidor is None
