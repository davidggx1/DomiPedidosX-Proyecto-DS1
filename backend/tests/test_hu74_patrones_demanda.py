"""Pruebas de HU-74 · Patrones de demanda (SCRUM-164)."""
from datetime import datetime
from decimal import Decimal

import pytest
from django.contrib.auth.models import Group
from django.utils import timezone
from rest_framework.test import APIClient

from pedidos.models import EstadoPedido as E, Factura, MetodoPago, Pedido
from sedes.models import Ciudad, Sede
from usuarios.models import Usuario
from usuarios.roles import ADMINISTRADOR, OPERADOR

pytestmark = pytest.mark.django_db

URL = "/api/pedidos/reportes/demanda/"
# Del lunes 9 al domingo 15 de noviembre de 2026
SEMANA = {"desde": "2026-11-09", "hasta": "2026-11-15"}
_folio = iter(range(1, 10_000))


def _sede(nombre):
    ciudad, _ = Ciudad.objects.get_or_create(nombre="Cali")
    return Sede.objects.create(
        ciudad=ciudad, nombre=nombre, direccion="Calle 1 # 2-3", latitud=3.45, longitud=-76.53,
        barrio="Centro", telefono="3000000000", correo=f"{nombre.lower()}@correo.com",
    )


def _pedido(sede, cuando, total="10000", estado=E.ENTREGADO, con_factura=True):
    """Pedido creado en `cuando` (hora local de Bogotá) con una factura de `total`."""
    pedido = Pedido.objects.create(sede=sede, numero_pedido=f"P-{next(_folio)}", estado=estado)
    Pedido.objects.filter(pk=pedido.pk).update(fecha_creacion=timezone.make_aware(cuando))
    if con_factura:
        Factura.objects.create(
            pedido=pedido, numero=f"F-{pedido.numero_pedido}", subtotal=Decimal(total), iva=Decimal("0"),
            costo_domicilio=Decimal("0"), valor_descuento=Decimal("0"), total=Decimal(total),
            metodo_pago=MetodoPago.TARJETA,
        )
    return pedido


def _con_rol(rol):
    usuario = Usuario.objects.create_user(username=f"{rol}@correo.com", email=f"{rol}@correo.com", password="x")
    usuario.groups.add(Group.objects.get_or_create(name=rol)[0])
    api = APIClient()
    api.force_authenticate(usuario)
    return api


@pytest.fixture
def m():
    centro, sur = _sede("Centro"), _sede("Sur")
    # Viernes 13 a las 19 h: la hora pico (3 pedidos)
    for minuto in (5, 20, 45):
        _pedido(centro, datetime(2026, 11, 13, 19, minuto), total="20000")
    # Martes 10 a las 12 h, en las dos sedes
    _pedido(centro, datetime(2026, 11, 10, 12, 30), total="15000")
    _pedido(sur, datetime(2026, 11, 10, 12, 10), total="5000")
    # Martes 10 a las 23:30 hora local (en UTC ya es miércoles): debe quedar en martes 23 h
    _pedido(centro, datetime(2026, 11, 10, 23, 30), total="8000")
    # No cuentan: cancelado, sin factura y fuera del rango
    _pedido(centro, datetime(2026, 11, 13, 19, 50), estado=E.CANCELADO)
    _pedido(centro, datetime(2026, 11, 13, 19, 55), con_factura=False)
    _pedido(centro, datetime(2026, 11, 20, 19, 0))
    return {"centro": centro, "sur": sur, "admin": _con_rol(ADMINISTRADOR)}


def _get(m, **params):
    return m["admin"].get(URL, {**SEMANA, **params})


def _celda(datos, dia, hora):
    return next(c for c in datos["celdas"] if c["dia"] == dia and c["hora"] == hora)


def test_la_cuadricula_tiene_7_dias_por_24_horas(m):
    datos = _get(m).data

    assert len(datos["celdas"]) == 7 * 24
    assert [d["nombre"] for d in datos["por_dia"]] == [
        "Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo",
    ]
    assert [h["hora"] for h in datos["por_hora"]] == list(range(24))


def test_cuenta_pedidos_y_ventas_por_dia_y_hora(m):
    datos = _get(m).data

    assert _celda(datos, 5, 19) == {
        "dia": 5, "hora": 19, "pedidos": 3, "ventas": "60000.00", "fechas": ["2026-11-13"],
    }
    assert _celda(datos, 2, 12) == {
        "dia": 2, "hora": 12, "pedidos": 2, "ventas": "20000.00", "fechas": ["2026-11-10"],
    }
    assert _celda(datos, 1, 12)["pedidos"] == 0
    assert datos["totales"] == {"pedidos": 6, "ventas": "88000.00"}


def test_usa_la_hora_local_y_no_la_de_utc(m):
    datos = _get(m).data

    assert _celda(datos, 2, 23)["pedidos"] == 1  # martes 23 h en Bogotá
    assert _celda(datos, 2, 23)["fechas"] == ["2026-11-10"]  # la fecha también es la local
    assert _celda(datos, 3, 4)["pedidos"] == 0  # no se pasa al miércoles 4 h (UTC)


def test_cada_celda_dice_de_que_fechas_salieron_sus_pedidos(m):
    # Otro viernes a las 19 h, en una semana distinta dentro del rango
    _pedido(m["centro"], datetime(2026, 11, 20, 19, 30), total="20000")

    datos = m["admin"].get(URL, {"desde": "2026-11-09", "hasta": "2026-11-22"}).data

    assert _celda(datos, 5, 19)["pedidos"] == 5  # 3 del viernes 13 y 2 del viernes 20
    assert _celda(datos, 5, 19)["fechas"] == ["2026-11-13", "2026-11-20"]
    assert _celda(datos, 1, 12)["fechas"] == []


def test_no_cuenta_cancelados_sin_factura_ni_fuera_del_rango(m):
    datos = _get(m).data

    # Solo los 3 válidos del viernes a las 19 h (el cancelado y el sin factura no suman)
    assert _celda(datos, 5, 19)["pedidos"] == 3
    assert datos["totales"]["pedidos"] == 6


def test_dia_y_hora_pico(m):
    datos = _get(m).data

    assert datos["dia_pico"] == {"dia": 5, "nombre": "Viernes", "pedidos": 3, "ventas": "60000.00"}
    assert datos["hora_pico"] == {"hora": 19, "pedidos": 3, "ventas": "60000.00"}


def test_empate_en_pedidos_gana_la_de_mas_ventas(m):
    por_dia = {d["nombre"]: d for d in _get(m).data["por_dia"]}

    # Martes y viernes tienen 3 pedidos cada uno; el viernes vendió más
    assert por_dia["Martes"]["pedidos"] == por_dia["Viernes"]["pedidos"] == 3
    assert por_dia["Martes"]["ventas"] == "28000.00"
    assert _get(m).data["dia_pico"]["nombre"] == "Viernes"


def test_filtra_por_sede(m):
    datos = _get(m, sede=m["sur"].pk).data

    assert datos["sede"] == {"id": m["sur"].pk, "nombre": "Sur"}
    assert datos["totales"] == {"pedidos": 1, "ventas": "5000.00"}
    assert datos["hora_pico"]["hora"] == 12


def test_sin_pedidos_en_el_rango(m):
    datos = m["admin"].get(URL, {"desde": "2026-10-01", "hasta": "2026-10-07"}).data

    assert datos["sin_datos"] is True
    assert datos["mensaje"] == "No hay pedidos en el rango seleccionado."
    assert datos["dia_pico"] is None and datos["hora_pico"] is None
    assert all(c["pedidos"] == 0 for c in datos["celdas"])


@pytest.mark.parametrize("params, codigo", [
    ({"desde": "2026-11-15", "hasta": "2026-11-09"}, 400),
    ({"desde": "15/11/2026"}, 400),
    ({"sede": "abc"}, 400),
    ({"sede": "999"}, 404),
])
def test_parametros_invalidos(m, params, codigo):
    assert _get(m, **params).status_code == codigo


def test_solo_el_administrador(m):
    assert _con_rol(OPERADOR).get(URL, SEMANA).status_code == 403
    assert APIClient().get(URL, SEMANA).status_code == 401
