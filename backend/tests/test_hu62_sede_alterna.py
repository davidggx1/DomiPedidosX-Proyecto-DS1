"""HU-62: alternate sede or next slot when the sede of the customer is blocked."""
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from itertools import count
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest
from django.contrib.auth.models import Group
from django.utils import timezone
from rest_framework.test import APIClient

from inventario.models import InventarioProducto
from menu.models import CategoriaMenu, Producto
from pedidos.alternativas import (
    DIAS_ES,
    MESES_ES,
    proximo_inicio_de_franja,
    texto_de_inicio,
)
from pedidos.capacidad import DIAS
from pedidos.models import EstadoPedido, Pedido
from sedes.models import CapacidadSede, Ciudad, Sede, ZonaCobertura
from usuarios.models import Cliente, DireccionEntrega, Usuario

pytestmark = pytest.mark.django_db

URL = "/api/pedidos/alternativas-capacidad/"
TODOS_LOS_DIAS = "lunes,martes,miercoles,jueves,viernes,sabado,domingo"
BOGOTA = ZoneInfo("America/Bogota")
_folios = count(1)


def _sede(nombre, ciudad, activa=True):
    return Sede.objects.create(
        ciudad=ciudad, nombre=nombre, direccion=f"Calle {nombre}", latitud=3.45,
        longitud=-76.53, barrio="Granada", telefono="3000000000", correo=f"{nombre}@correo.com".replace(" ", ""),
        activa=activa,
    )


def _zona(sede, lat, lon, radio=5, tarifa="3000", minimo="10000", tiempo=40):
    return ZonaCobertura.objects.create(
        sede=sede, nombre="Zona", radio=radio, centro_latitud=lat, centro_longitud=lon,
        tarifa_domicilio=Decimal(tarifa), tiempo_estimado=tiempo, pedido_minimo=Decimal(minimo),
    )


def _franja(sede, maximo=3, dias=TODOS_LOS_DIAS, inicio=time(0, 0), fin=time(23, 59, 59)):
    return CapacidadSede.objects.create(
        sede=sede, hora_inicio=inicio, hora_fin=fin, dias_semana=dias,
        max_pedidos_simultaneos=maximo, umbral_alerta=maximo,
    )


def _llenar(sede, cantidad):
    for _ in range(cantidad):
        Pedido.objects.create(
            numero_pedido=f"A-{next(_folios)}", sede=sede, estado=EstadoPedido.RECIBIDO
        )


def _personal(rol):
    usuario = Usuario.objects.create_user(username=f"{rol}@correo.com", email=f"{rol}@correo.com", password="ClaveSegura2026")
    usuario.groups.add(Group.objects.get_or_create(name=rol)[0])
    return usuario


def _http(usuario=None):
    c = APIClient()
    if usuario:
        c.force_authenticate(user=usuario)
    return c


def _cliente(ciudad, correo="cli@correo.com", celular="3001234567"):
    usuario = Usuario.objects.create_user(username=correo, email=correo, password="ClaveSegura2026")
    cliente = Cliente.objects.create(
        usuario=usuario, tipo_documento="CC", num_documento=correo[:8], nombres="Ana",
        apellidos="Prueba", celular=celular, fecha_nacimiento=date(2000, 1, 1),
    )
    direccion = DireccionEntrega.objects.create(
        ciudad=ciudad, cliente=cliente, direccion="Calle 5 # 6-7", latitud=3.46, longitud=-76.53,
    )
    return usuario, direccion


@pytest.fixture
def m():
    ciudad = Ciudad.objects.create(nombre="Cali")
    norte = _sede("Norte", ciudad)  # the sede of the customer
    centro = _sede("Centro", ciudad)  # near, with capacity
    sur = _sede("Sur", ciudad)  # farther, with capacity
    lejana = _sede("Lejana", ciudad)  # does not cover the address
    cerrada = _sede("Cerrada", ciudad, activa=False)
    _zona(norte, 3.46, -76.53)
    _zona(centro, 3.461, -76.53, tarifa="2500", minimo="8000", tiempo=25)
    _zona(sur, 3.50, -76.53, radio=10, tarifa="6000", minimo="15000", tiempo=55)
    _zona(lejana, 4.50, -76.50, radio=2)
    _zona(cerrada, 3.46, -76.53)
    for sede in (norte, centro, sur, lejana, cerrada):
        _franja(sede, maximo=3)
    usuario, direccion = _cliente(ciudad)
    return SimpleNamespace(
        ciudad=ciudad, norte=norte, centro=centro, sur=sur, lejana=lejana, cerrada=cerrada,
        usuario=usuario, direccion=direccion,
    )


def _pedir(m, sede=None, productos=(), usuario=None, direccion=None):
    return _http(usuario or m.usuario).post(
        URL,
        {
            "sede_id": (sede or m.norte).pk,
            "direccion_id": (direccion or m.direccion).pk,
            "productos": list(productos),
        },
        format="json",
    )


# --- Criterio 1: sede principal al 100% → sugiere otra cercana con cobertura y cupo -----

def test_sede_saturada_sugiere_las_sedes_cercanas_con_cobertura_y_cupo(m):
    _llenar(m.norte, 3)

    r = _pedir(m)

    assert r.status_code == 200
    assert r.data["bloqueada"] is True
    assert r.data["capacidad"]["estado"] == "saturada"
    # nearest first; the far one has no coverage, the closed one is inactive, and
    # the saturated sede itself is not suggested
    assert [a["sede"]["nombre"] for a in r.data["alternativas"]] == ["Centro", "Sur"]


def test_cada_alternativa_trae_la_tarifa_el_minimo_y_el_tiempo_de_su_zona(m):
    _llenar(m.norte, 3)

    centro, sur = _pedir(m).data["alternativas"]

    assert (centro["tarifa_domicilio"], centro["pedido_minimo"], centro["tiempo_estimado"]) == (2500.0, 8000.0, 25)
    assert (sur["tarifa_domicilio"], sur["pedido_minimo"], sur["tiempo_estimado"]) == (6000.0, 15000.0, 55)
    assert centro["distancia_km"] < sur["distancia_km"]
    assert centro["cupos_libres"] == 3
    assert centro["sede"]["id"] == m.centro.pk


def test_no_sugiere_una_sede_que_tambien_esta_saturada_o_sin_franja(m):
    _llenar(m.norte, 3)
    _llenar(m.centro, 3)
    CapacidadSede.objects.filter(sede=m.sur).delete()

    r = _pedir(m)

    assert r.data["alternativas"] == []


def test_los_cupos_libres_descuentan_los_pedidos_en_curso(m):
    _llenar(m.norte, 3)
    _llenar(m.centro, 2)

    centro = _pedir(m).data["alternativas"][0]

    assert centro["sede"]["nombre"] == "Centro"
    assert centro["cupos_libres"] == 1


def test_avisa_que_productos_del_carrito_no_tendria_la_otra_sede(m):
    _llenar(m.norte, 3)
    categoria = CategoriaMenu.objects.create(nombre="Platos")
    producto = Producto.objects.create(
        categoria=categoria, nombre="Clásica", precio_base=15000, tiempo_preparacion=10,
        tipo_control_stock=Producto.TipoControlStock.PRODUCTO,
    )
    InventarioProducto.objects.create(sede=m.centro, producto=producto, stock_actual=0, stock_minimo=0, disponible=False)
    InventarioProducto.objects.create(sede=m.sur, producto=producto, stock_actual=20, stock_minimo=5, disponible=True)

    centro, sur = _pedir(m, productos=[producto.pk]).data["alternativas"]

    assert centro["no_disponibles"] == [{"id": producto.pk, "nombre": "Clásica"}]
    assert sur["no_disponibles"] == []


# --- Criterio 2: sin alternativas, informa la hora exacta de la siguiente franja -------

def test_sin_alternativas_informa_la_hora_exacta_de_la_siguiente_franja(m):
    _llenar(m.norte, 3)
    for sede in (m.centro, m.sur):
        CapacidadSede.objects.filter(sede=sede).delete()

    r = _pedir(m)

    assert r.data["alternativas"] == []
    siguiente = r.data["siguiente_franja"]
    # the slot of Norte is all day: the next one starts tomorrow at midnight
    manana = timezone.localdate() + timedelta(days=1)
    inicio = datetime.fromisoformat(siguiente["inicio"])
    assert (inicio.date(), inicio.time()) == (manana, time(0, 0))
    assert siguiente["texto"] == "mañana a las 12:00 a. m."


def test_la_siguiente_franja_tambien_va_cuando_si_hay_alternativas(m):
    _llenar(m.norte, 3)

    r = _pedir(m)

    assert r.data["alternativas"]
    assert r.data["siguiente_franja"] is not None


def test_sin_franja_ahora_tambien_ofrece_alternativas_y_la_proxima_franja(m):
    # Norte only has slots three days from now
    CapacidadSede.objects.filter(sede=m.norte).delete()
    futuro = timezone.localdate() + timedelta(days=3)
    _franja(m.norte, dias=DIAS[futuro.weekday()], inicio=time(9, 0), fin=time(12, 0))

    r = _pedir(m)

    assert r.data["bloqueada"] is True
    assert r.data["capacidad"]["estado"] == "sin_franja"
    assert [a["sede"]["nombre"] for a in r.data["alternativas"]] == ["Centro", "Sur"]
    inicio = datetime.fromisoformat(r.data["siguiente_franja"]["inicio"])
    assert (inicio.date(), inicio.time()) == (futuro, time(9, 0))
    esperado = f"el {DIAS_ES[futuro.weekday()]} {futuro.day} de {MESES_ES[futuro.month - 1]} a las 9:00 a. m."
    assert r.data["siguiente_franja"]["texto"] == esperado


def test_una_sede_sin_ninguna_franja_no_tiene_siguiente(m):
    CapacidadSede.objects.filter(sede=m.norte).delete()

    r = _pedir(m)

    assert r.data["bloqueada"] is True
    assert r.data["siguiente_franja"] is None
    assert r.data["alternativas"]


def test_si_la_sede_tiene_cupo_no_hay_nada_que_sugerir(m):
    _llenar(m.norte, 2)

    r = _pedir(m)

    assert r.data["bloqueada"] is False
    assert r.data["capacidad"]["estado"] == "disponible"
    assert r.data["alternativas"] == []
    assert r.data["siguiente_franja"] is None


# --- Permisos y datos --------------------------------------------------------------------

def test_sin_sesion_recibe_401(m):
    assert _http().post(URL, {"sede_id": m.norte.pk, "direccion_id": m.direccion.pk}, format="json").status_code == 401


@pytest.mark.parametrize("rol", ["operador", "administrador", "cocina", "repartidor"])
def test_solo_los_clientes_pueden_consultarlo(m, rol):
    r = _http(_personal(rol)).post(URL, {"sede_id": m.norte.pk, "direccion_id": m.direccion.pk}, format="json")

    assert r.status_code == 403


def test_una_sede_inexistente_o_inactiva_da_404(m):
    assert _pedir(m, sede=SimpleNamespace(pk=99999)).status_code == 404
    assert _pedir(m, sede=m.cerrada).status_code == 404


def test_la_direccion_debe_ser_del_cliente(m):
    _, ajena = _cliente(m.ciudad, "otro@correo.com", "3009999999")

    r = _pedir(m, direccion=ajena)

    assert r.status_code == 400
    assert "direccion_id" in r.data


def test_los_productos_deben_ser_ids_numericos(m):
    r = _http(m.usuario).post(
        URL, {"sede_id": m.norte.pk, "direccion_id": m.direccion.pk, "productos": ["a"]}, format="json"
    )

    assert r.status_code == 400


# --- Cálculo del inicio de la siguiente franja (sin depender del reloj) ---------------

LUNES_10AM = datetime(2026, 11, 9, 10, 0, tzinfo=BOGOTA)


def test_toma_la_siguiente_franja_de_hoy(m):
    CapacidadSede.objects.filter(sede=m.norte).delete()  # the fixture has an all-day slot
    _franja(m.norte, dias="lunes", inicio=time(8, 0), fin=time(12, 0))
    _franja(m.norte, dias="lunes", inicio=time(14, 0), fin=time(18, 0))

    inicio = proximo_inicio_de_franja(m.norte, LUNES_10AM)

    # the one that started at 8:00 is running now, it is not the next one
    assert inicio == datetime(2026, 11, 9, 14, 0, tzinfo=BOGOTA)


def test_pasa_al_dia_siguiente_si_ya_no_quedan_franjas_hoy(m):
    CapacidadSede.objects.filter(sede=m.norte).delete()  # the fixture has an all-day slot
    _franja(m.norte, dias="lunes,martes", inicio=time(8, 0), fin=time(12, 0))

    inicio = proximo_inicio_de_franja(m.norte, datetime(2026, 11, 9, 19, 0, tzinfo=BOGOTA))

    assert inicio == datetime(2026, 11, 10, 8, 0, tzinfo=BOGOTA)


def test_si_solo_hay_franja_el_mismo_dia_de_la_semana_espera_ocho_dias(m):
    CapacidadSede.objects.filter(sede=m.norte).delete()  # the fixture has an all-day slot
    _franja(m.norte, dias="lunes", inicio=time(8, 0), fin=time(12, 0))

    inicio = proximo_inicio_de_franja(m.norte, datetime(2026, 11, 9, 19, 0, tzinfo=BOGOTA))

    assert inicio == datetime(2026, 11, 16, 8, 0, tzinfo=BOGOTA)


def test_elige_la_franja_que_empieza_primero(m):
    CapacidadSede.objects.filter(sede=m.norte).delete()  # the fixture has an all-day slot
    _franja(m.norte, dias="martes", inicio=time(15, 0), fin=time(18, 0))
    _franja(m.norte, dias="martes", inicio=time(9, 30), fin=time(12, 0))
    _franja(m.norte, dias="miercoles", inicio=time(7, 0), fin=time(8, 0))

    inicio = proximo_inicio_de_franja(m.norte, LUNES_10AM)

    assert inicio == datetime(2026, 11, 10, 9, 30, tzinfo=BOGOTA)


def test_sin_franjas_no_hay_siguiente(m):
    CapacidadSede.objects.filter(sede=m.norte).delete()

    assert proximo_inicio_de_franja(m.norte, LUNES_10AM) is None


def test_las_franjas_de_otras_sedes_no_cuentan(m):
    CapacidadSede.objects.filter(sede=m.norte).delete()
    _franja(m.centro, dias="lunes", inicio=time(14, 0), fin=time(18, 0))

    assert proximo_inicio_de_franja(m.norte, LUNES_10AM) is None


# --- Texto de la hora --------------------------------------------------------------------

@pytest.mark.parametrize(
    "inicio, esperado",
    [
        (datetime(2026, 11, 9, 15, 0, tzinfo=BOGOTA), "hoy a las 3:00 p. m."),
        (datetime(2026, 11, 9, 13, 0, tzinfo=BOGOTA), "hoy a la 1:00 p. m."),
        (datetime(2026, 11, 9, 12, 30, tzinfo=BOGOTA), "hoy a las 12:30 p. m."),
        (datetime(2026, 11, 10, 0, 0, tzinfo=BOGOTA), "mañana a las 12:00 a. m."),
        (datetime(2026, 11, 10, 11, 5, tzinfo=BOGOTA), "mañana a las 11:05 a. m."),
        (datetime(2026, 11, 16, 11, 0, tzinfo=BOGOTA), "el lunes 16 de noviembre a las 11:00 a. m."),
        (datetime(2026, 11, 14, 9, 0, tzinfo=BOGOTA), "el sábado 14 de noviembre a las 9:00 a. m."),
    ],
)
def test_texto_de_la_hora_exacta(inicio, esperado):
    assert texto_de_inicio(inicio, LUNES_10AM) == esperado
