"""Pruebas de HU-70 · Panel de indicadores del día (SCRUM-139)."""
from datetime import time, timedelta
from decimal import Decimal

import pytest
from django.contrib.auth.models import Group
from django.utils import timezone
from rest_framework.test import APIClient

from pedidos.models import EstadoPedido as E
from pedidos.models import Factura, HistorialEstadoPedido, MetodoPago, Pedido
from sedes.models import CapacidadSede, Ciudad, Sede
from usuarios.models import Empleado, Usuario
from usuarios.roles import ADMINISTRADOR, OPERADOR

pytestmark = pytest.mark.django_db

URL = "/api/pedidos/indicadores/"
TODOS_LOS_DIAS = "lunes,martes,miercoles,jueves,viernes,sabado,domingo"


# --- Datos de prueba ------------------------------------------------------------


def _sede(nombre, activa=True):
    ciudad, _ = Ciudad.objects.get_or_create(nombre="Cali")
    return Sede.objects.create(
        ciudad=ciudad, nombre=nombre, direccion="Calle 1 # 2-3", latitud=3.45, longitud=-76.53,
        barrio="Centro", telefono="3000000000", correo=f"{nombre.lower().replace(' ', '')}@correo.com",
        activa=activa,
    )


@pytest.fixture
def centro():
    return _sede("Centro")


@pytest.fixture
def sur():
    return _sede("Sur")


@pytest.fixture
def admin():
    usuario = Usuario.objects.create_user(username="admin@correo.com", email="admin@correo.com", password="x")
    usuario.groups.add(Group.objects.get_or_create(name=ADMINISTRADOR)[0])
    api = APIClient()
    api.force_authenticate(usuario)
    return api


def _pedido(sede, numero, estado=E.RECIBIDO, total="20000", hace_horas=0, entregado_en_min=None):
    """Pedido creado hoy (o `hace_horas` antes) con factura; si `entregado_en_min`, se entregó."""
    pedido = Pedido.objects.create(sede=sede, numero_pedido=numero, estado=estado)
    creado = timezone.now() - timedelta(hours=hace_horas)
    Pedido.objects.filter(pk=pedido.pk).update(fecha_creacion=creado)
    if total is not None:
        Factura.objects.create(
            pedido=pedido, numero=f"F-{numero}", subtotal=Decimal(total), iva=Decimal("0"),
            costo_domicilio=Decimal("0"), total=Decimal(total), metodo_pago=MetodoPago.EFECTIVO,
        )
    if entregado_en_min is not None:
        paso = HistorialEstadoPedido.objects.create(pedido=pedido, estado=E.ENTREGADO)
        HistorialEstadoPedido.objects.filter(pk=paso.pk).update(fecha_hora=creado + timedelta(minutes=entregado_en_min))
    return pedido


def _a_media_jornada():
    """Hora fija del día de hoy, para que 'hoy' no dependa de la hora en que corren las pruebas."""
    return timezone.localtime().replace(hour=12, minute=0, second=0, microsecond=0)


@pytest.fixture(autouse=True)
def mediodia(monkeypatch):
    # Los pedidos "de hoy" se crean a las 12:00 locales, sin importar la hora real.
    ahora = _a_media_jornada()
    monkeypatch.setattr(timezone, "now", lambda: ahora)
    return ahora


# --- Criterio 1: métricas clave --------------------------------------------------


def test_muestra_pedidos_ventas_cancelaciones_y_tiempo_de_entrega(admin, centro):
    _pedido(centro, "P-1", estado=E.ENTREGADO, total="30000", hace_horas=2, entregado_en_min=40)
    _pedido(centro, "P-2", estado=E.ENTREGADO, total="20000", hace_horas=1, entregado_en_min=20)
    _pedido(centro, "P-3", estado=E.EN_PREPARACION, total="10000")
    _pedido(centro, "P-4", estado=E.CANCELADO, total="50000")

    datos = admin.get(URL).data

    assert datos["pedidos"] == 4
    assert Decimal(datos["ventas"]) == Decimal("60000")  # sin el cancelado
    assert datos["cancelaciones"] == 1
    assert datos["entregados"] == 2
    assert datos["tiempo_promedio_entrega"] == 30  # (40 + 20) / 2


def test_muestra_la_ocupacion_de_cocina_de_cada_sede(admin, centro, sur):
    CapacidadSede.objects.create(
        sede=centro, hora_inicio=time(0, 0), hora_fin=time(23, 59, 59), dias_semana=TODOS_LOS_DIAS,
        max_pedidos_simultaneos=10, umbral_alerta=8,
    )
    for i in range(3):
        _pedido(centro, f"P-{i}", estado=E.EN_PREPARACION)

    sedes = {s["nombre"]: s for s in admin.get(URL).data["sedes"]}

    assert sedes["Centro"]["ocupacion"] == {"activos": 3, "maximo": 10, "porcentaje": 30, "estado": "disponible"}
    assert sedes["Sur"]["ocupacion"]["estado"] == "sin_franja"
    assert sedes["Sur"]["ocupacion"]["maximo"] is None


# --- Criterio 2: sede individual o consolidado -----------------------------------


def test_el_consolidado_suma_todas_las_sedes_activas(admin, centro, sur):
    cerrada = _sede("Cerrada", activa=False)
    _pedido(centro, "P-1", total="10000")
    _pedido(sur, "P-2", total="15000")
    _pedido(cerrada, "P-3", total="99000")

    datos = admin.get(URL).data

    assert datos["pedidos"] == 2
    assert Decimal(datos["ventas"]) == Decimal("25000")
    assert [s["nombre"] for s in datos["sedes"]] == ["Centro", "Sur"]


def test_se_puede_ver_una_sola_sede(admin, centro, sur):
    _pedido(centro, "P-1", total="10000")
    _pedido(sur, "P-2", total="15000")

    datos = admin.get(URL, {"sede": sur.pk}).data

    assert datos["pedidos"] == 1
    assert Decimal(datos["ventas"]) == Decimal("15000")
    assert [s["nombre"] for s in datos["sedes"]] == ["Sur"]


def test_el_tiempo_promedio_del_consolidado_pondera_todas_las_entregas(admin, centro, sur):
    _pedido(centro, "P-1", estado=E.ENTREGADO, entregado_en_min=10)
    _pedido(centro, "P-2", estado=E.ENTREGADO, entregado_en_min=20)
    _pedido(sur, "P-3", estado=E.ENTREGADO, entregado_en_min=60)

    datos = admin.get(URL).data

    assert datos["tiempo_promedio_entrega"] == 30  # (10 + 20 + 60) / 3, no el promedio de promedios


# --- Criterio 3: las ventas no cuentan los cancelados ----------------------------


def test_un_pedido_cancelado_no_suma_ventas_pero_si_cuenta_como_pedido(admin, centro):
    _pedido(centro, "P-1", estado=E.CANCELADO, total="80000")

    datos = admin.get(URL).data

    assert datos["pedidos"] == 1
    assert datos["cancelaciones"] == 1
    assert Decimal(datos["ventas"]) == Decimal("0")


# --- Criterio 4: días sin operación y coherencia con la HU-67 --------------------


def test_un_dia_sin_pedidos_marca_cero_sin_errores(admin, centro):
    respuesta = admin.get(URL)

    assert respuesta.status_code == 200
    datos = respuesta.data
    assert (datos["pedidos"], datos["cancelaciones"], datos["entregados"]) == (0, 0, 0)
    assert Decimal(datos["ventas"]) == 0
    assert datos["tiempo_promedio_entrega"] == 0


def test_sin_sedes_activas_tampoco_falla(admin):
    datos = admin.get(URL).data

    assert datos["pedidos"] == 0
    assert datos["sedes"] == []


def test_los_pedidos_de_ayer_no_cuentan(admin, centro):
    _pedido(centro, "P-AYER", hace_horas=24)
    _pedido(centro, "P-HOY")

    assert admin.get(URL).data["pedidos"] == 1


def test_el_total_coincide_con_pedidos_del_dia(admin, centro, sur):
    for i, sede in enumerate([centro, centro, sur, sur, sur]):
        _pedido(sede, f"P-{i}", estado=E.CANCELADO if i == 0 else E.RECIBIDO)
    _pedido(centro, "P-AYER", hace_horas=24)

    resumen = admin.get("/api/pedidos/resumen-dia/").data
    indicadores = admin.get(URL).data

    assert indicadores["pedidos"] == sum(sede["total"] for sede in resumen["sedes"])
    for sede in indicadores["sedes"]:
        en_resumen = next(s for s in resumen["sedes"] if s["sede_id"] == sede["sede_id"])
        assert sede["pedidos"] == en_resumen["total"]


# --- Permisos y errores ------------------------------------------------------------


def test_solo_el_administrador(centro):
    usuario = Usuario.objects.create_user(username="op@correo.com", email="op@correo.com", password="x")
    usuario.groups.add(Group.objects.get_or_create(name=OPERADOR)[0])
    Empleado.objects.create(
        usuario=usuario, sede=centro, tipo_documento="CC", num_documento="1234567",
        nombres="Op", apellidos="Prueba", celular="3001234567", direccion="Calle 4",
    )
    api = APIClient()
    api.force_authenticate(usuario)

    assert api.get(URL).status_code == 403
    assert APIClient().get(URL).status_code == 401


def test_sede_invalida_o_inexistente(admin):
    assert admin.get(URL, {"sede": "abc"}).status_code == 400
    assert admin.get(URL, {"sede": 99999}).status_code == 404
