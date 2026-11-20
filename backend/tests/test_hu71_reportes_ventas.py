"""Pruebas de HU-71 · Reportes de ventas (SCRUM-141)."""
from datetime import date, datetime
from decimal import Decimal

import pytest
from django.contrib.auth.models import Group
from django.utils import timezone
from rest_framework.test import APIClient

from menu.models import CategoriaMenu, Producto
from pedidos.models import DetallePedido, EstadoPedido as E, Factura, MetodoPago, Pedido
from promociones.models import Combo
from sedes.models import Ciudad, Sede, ZonaCobertura
from usuarios.models import Usuario
from usuarios.roles import ADMINISTRADOR, OPERADOR

pytestmark = pytest.mark.django_db

URL = "/api/pedidos/reportes/ventas/"
SEMANA = {"desde": "2026-11-09", "hasta": "2026-11-15"}
_folio = iter(range(1, 10_000))


def _sede(nombre):
    ciudad, _ = Ciudad.objects.get_or_create(nombre="Cali")
    return Sede.objects.create(
        ciudad=ciudad, nombre=nombre, direccion="Calle 1 # 2-3", latitud=3.45, longitud=-76.53,
        barrio="Centro", telefono="3000000000", correo=f"{nombre.lower()}@correo.com",
    )


def _zona(sede, nombre):
    return ZonaCobertura.objects.create(
        sede=sede, nombre=nombre, radio=5, centro_latitud=3.45, centro_longitud=-76.53,
        tarifa_domicilio=Decimal("3000"), tiempo_estimado=40, pedido_minimo=Decimal("0"),
    )


def _pedido(sede, lineas, dia=date(2026, 11, 10), estado=E.ENTREGADO, zona=None,
            descuento="0", domicilio="0"):
    """Pedido con factura: `lineas` = [(producto | combo, cantidad, precio_unitario)]."""
    pedido = Pedido.objects.create(
        sede=sede, numero_pedido=f"P-{next(_folio)}", estado=estado, zona_cobertura=zona,
    )
    creado = timezone.make_aware(datetime.combine(dia, datetime.min.time()).replace(hour=12))
    Pedido.objects.filter(pk=pedido.pk).update(fecha_creacion=creado)
    subtotal = Decimal("0")
    for item, cantidad, precio in lineas:
        linea = Decimal(precio) * cantidad
        subtotal += linea
        DetallePedido.objects.create(
            pedido=pedido, cantidad=cantidad, precio_unitario=Decimal(precio), subtotal=linea,
            **({"combo": item} if isinstance(item, Combo) else {"producto": item}),
        )
    descuento, domicilio = Decimal(descuento), Decimal(domicilio)
    Factura.objects.create(
        pedido=pedido, numero=f"F-{pedido.numero_pedido}", subtotal=subtotal, iva=Decimal("0"),
        costo_domicilio=domicilio, valor_descuento=descuento, total=subtotal - descuento + domicilio,
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
    platos, bebidas = CategoriaMenu.objects.create(nombre="Platos"), CategoriaMenu.objects.create(nombre="Bebidas")
    hamburguesa = Producto.objects.create(categoria=platos, nombre="Hamburguesa", precio_base=20000, tiempo_preparacion=15)
    perro = Producto.objects.create(categoria=platos, nombre="Perro", precio_base=12000, tiempo_preparacion=10)
    gaseosa = Producto.objects.create(categoria=bebidas, nombre="Gaseosa", precio_base=4000, tiempo_preparacion=1)
    combo = Combo.objects.create(
        nombre="Combo pareja", precio=30000, fecha_inicio=date(2026, 11, 1), fecha_vencimiento=date(2026, 12, 1),
    )
    norte = _zona(centro, "Norte")

    # Centro, zona Norte: 2 hamburguesas + 1 gaseosa, con descuento y domicilio
    _pedido(centro, [(hamburguesa, 2, "20000"), (gaseosa, 1, "4000")], zona=norte, descuento="4400", domicilio="3000")
    # Centro, mostrador (sin zona): 1 perro + 1 combo
    _pedido(centro, [(perro, 1, "12000"), (combo, 1, "30000")])
    # Sur, en preparación (cuenta: no está cancelado)
    _pedido(sur, [(hamburguesa, 1, "20000")], estado=E.EN_PREPARACION)
    # No cuentan: cancelado y fuera del rango
    _pedido(centro, [(hamburguesa, 5, "20000")], estado=E.CANCELADO)
    _pedido(centro, [(hamburguesa, 5, "20000")], dia=date(2026, 11, 20))
    return {"centro": centro, "sur": sur, "admin": _con_rol(ADMINISTRADOR)}


def _get(m, **params):
    return m["admin"].get(URL, {**SEMANA, **params})


def _por_nombre(datos):
    return {g["nombre"]: g for g in datos["grupos"]}


# --- Criterio 2: la suma concuerda con lo facturado por pedidos válidos ----------


def test_los_totales_salen_de_las_facturas_validas(m):
    totales = _get(m).data["totales"]

    # (44000 - 4400 + 3000) + 42000 + 20000; el cancelado y el de fuera del rango no suman
    assert totales["pedidos"] == 3
    assert totales["subtotal"] == "106000.00"
    assert totales["descuentos"] == "4400.00"
    assert totales["domicilio"] == "3000.00"
    assert totales["total"] == "104600.00"
    assert totales["ticket_promedio"] == "34866.67"


@pytest.mark.parametrize("agrupar", ["sede", "zona"])
def test_por_sede_y_zona_los_grupos_suman_el_total(m, agrupar):
    datos = _get(m, agrupar=agrupar).data

    suma = sum(Decimal(g["ventas"]) for g in datos["grupos"])
    assert suma == Decimal(datos["totales"]["total"])
    assert datos["conciliacion"] is None


def test_por_sede(m):
    grupos = _por_nombre(_get(m, agrupar="sede").data)

    assert grupos["Centro"]["ventas"] == "84600.00"
    assert grupos["Centro"]["pedidos"] == 2
    assert grupos["Sur"]["ventas"] == "20000.00"
    assert grupos["Centro"]["porcentaje"] == "80.9"


def test_por_zona_los_pedidos_sin_zona_tienen_su_grupo(m):
    grupos = _por_nombre(_get(m, agrupar="zona").data)

    assert grupos["Norte · Centro"]["ventas"] == "42600.00"
    assert grupos["Sin zona (mostrador o teléfono) · Centro"]["ventas"] == "42000.00"
    assert grupos["Sin zona (mostrador o teléfono) · Sur"]["ventas"] == "20000.00"


def test_por_producto_cuenta_unidades_y_separa_los_combos(m):
    datos = _get(m, agrupar="producto").data
    grupos = _por_nombre(datos)

    h = grupos["Hamburguesa"]
    assert (h["unidades"], h["pedidos"], h["ventas"]) == (3, 2, "60000.00")
    assert grupos["Combo: Combo pareja"]["ventas"] == "30000.00"
    assert [g["nombre"] for g in datos["grupos"]][0] == "Hamburguesa"  # de mayor a menor


def test_por_categoria_los_combos_van_aparte(m):
    grupos = _por_nombre(_get(m, agrupar="categoria").data)

    assert grupos["Platos"]["ventas"] == "72000.00"
    assert grupos["Bebidas"]["ventas"] == "4000.00"
    assert grupos["Combos"]["ventas"] == "30000.00"


@pytest.mark.parametrize("agrupar", ["producto", "categoria"])
def test_la_conciliacion_lleva_de_las_lineas_al_total_facturado(m, agrupar):
    c = _get(m, agrupar=agrupar).data["conciliacion"]

    assert c == {
        "lineas": "106000.00", "descuentos": "4400.00", "domicilio": "3000.00",
        "ajustes": "0.00", "total": "104600.00",
    }
    total = Decimal(c["lineas"]) - Decimal(c["descuentos"]) + Decimal(c["domicilio"]) + Decimal(c["ajustes"])
    assert total == Decimal(c["total"])


def test_filtra_por_sede(m):
    datos = _get(m, agrupar="producto", sede=m["sur"].pk).data

    assert datos["sede"] == {"id": m["sur"].pk, "nombre": "Sur"}
    assert datos["totales"]["total"] == "20000.00"
    assert [g["nombre"] for g in datos["grupos"]] == ["Hamburguesa"]


def test_los_dos_extremos_del_rango_cuentan(m):
    _pedido(m["sur"], [], dia=date(2026, 11, 9))
    _pedido(m["sur"], [], dia=date(2026, 11, 15))

    assert _get(m).data["totales"]["pedidos"] == 5


# --- Criterio 3 y 4: rango inválido y rango sin ventas ---------------------------


def test_rechaza_inicio_posterior_al_fin(m):
    r = m["admin"].get(URL, {"desde": "2026-11-15", "hasta": "2026-11-09"})

    assert r.status_code == 400
    assert r.data["desde"] == "La fecha de inicio no puede ser posterior a la fecha de fin."


def test_sin_ventas_lo_avisa(m):
    r = m["admin"].get(URL, {"desde": "2026-10-01", "hasta": "2026-10-07"})

    assert r.status_code == 200
    assert r.data["sin_datos"] is True
    assert r.data["mensaje"] == "No hay ventas en el rango seleccionado."
    assert r.data["grupos"] == []


# --- Parámetros y permisos ---------------------------------------------------------


def test_agrupar_por_defecto_es_producto(m):
    assert _get(m).data["agrupar"] == "producto"


def test_agrupacion_invalida(m):
    r = _get(m, agrupar="cliente")
    assert r.status_code == 400
    assert "agrupar" in r.data


def test_sede_invalida_o_inexistente(m):
    assert _get(m, sede="abc").status_code == 400
    assert _get(m, sede="9999").status_code == 404


def test_solo_el_administrador(m):
    assert _con_rol(OPERADOR).get(URL, SEMANA).status_code == 403
    assert APIClient().get(URL, SEMANA).status_code == 401
