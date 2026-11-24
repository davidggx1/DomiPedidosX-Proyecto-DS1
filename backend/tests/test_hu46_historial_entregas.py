"""HU-46 · El repartidor consulta sus entregas por día y el dinero cobrado."""
from datetime import date, datetime, timedelta
from decimal import Decimal

import pytest
from django.contrib.auth.models import Group
from django.utils import timezone
from rest_framework.test import APIClient

from pedidos.models import EstadoFactura, EstadoPedido as E, Factura, HistorialEstadoPedido, MetodoPago, Pedido
from sedes.models import Ciudad, Sede
from usuarios.models import Cliente, Empleado, Repartidor, Usuario
from usuarios.roles import OPERADOR, REPARTIDOR

pytestmark = pytest.mark.django_db

URL = "/api/pedidos/mis-entregas/historial/"
HOY = date(2026, 11, 24)


@pytest.fixture(autouse=True)
def hoy_fijo(monkeypatch):
    """Las pruebas corren como si hoy fuera el 24 de noviembre de 2026 a las 20:00."""
    ahora = timezone.make_aware(datetime(2026, 11, 24, 20, 0))
    monkeypatch.setattr(timezone, "now", lambda: ahora)


def _hora(dia, hora):
    return timezone.make_aware(datetime.combine(dia, datetime.min.time()).replace(hour=hora))


@pytest.fixture
def sede():
    ciudad, _ = Ciudad.objects.get_or_create(nombre="Cali")
    return Sede.objects.create(
        ciudad=ciudad, nombre="Centro", direccion="Calle 1 # 2-3", latitud=3.45, longitud=-76.53,
        barrio="Granada", telefono="3000000000", correo="s@correo.com",
    )


def _empleado(rol, email, sede):
    usuario = Usuario.objects.create_user(username=email, email=email, password="x")
    usuario.groups.add(Group.objects.get_or_create(name=rol)[0])
    empleado = Empleado.objects.create(
        usuario=usuario, sede=sede, tipo_documento="CC", num_documento=email[:10], nombres="N",
        apellidos="A", celular="3001234567", direccion="Calle 4",
    )
    if rol == REPARTIDOR:
        return Repartidor.objects.create(empleado=empleado, disponible=True)
    return empleado


@pytest.fixture
def ana():
    usuario = Usuario.objects.create_user(username="ana@correo.com", email="ana@correo.com", password="x")
    return Cliente.objects.create(
        usuario=usuario, tipo_documento="CC", num_documento="1010", nombres="Ana", apellidos="Gómez",
        celular="3009998877", fecha_nacimiento=date(2000, 1, 1),
    )


def _entrega(sede, repartidor, cliente, numero, entregado, total, metodo=MetodoPago.EFECTIVO, recibido=None,
             estado=E.ENTREGADO):
    pedido = Pedido.objects.create(
        sede=sede, cliente=cliente, numero_pedido=numero, estado=estado, repartidor=repartidor,
        entrega_direccion="Calle 5 # 10-20", entrega_barrio="San Fernando",
    )
    Factura.objects.create(
        pedido=pedido, numero=f"F-{numero}", subtotal=total, iva=Decimal("0"), costo_domicilio=Decimal("0"),
        total=total, metodo_pago=metodo, estado_factura=EstadoFactura.PAGADA, monto_recaudado=recibido,
    )
    if entregado:
        paso = HistorialEstadoPedido.objects.create(pedido=pedido, estado=E.ENTREGADO)
        HistorialEstadoPedido.objects.filter(pk=paso.pk).update(fecha_hora=entregado)
    return pedido


def _http(repartidor):
    api = APIClient()
    api.force_authenticate(repartidor.empleado.usuario)
    return api


def test_sin_fechas_muestra_las_entregas_de_hoy_con_el_dinero(sede, ana):
    yo = _empleado(REPARTIDOR, "rep@correo.com", sede)
    _entrega(sede, yo, ana, "P-1", _hora(HOY, 12), Decimal("35000"), recibido=Decimal("50000"))
    _entrega(sede, yo, ana, "P-2", _hora(HOY, 18), Decimal("20000"), metodo=MetodoPago.TARJETA)
    _entrega(sede, yo, ana, "P-3", _hora(HOY - timedelta(days=1), 18), Decimal("99000"))

    datos = _http(yo).get(URL).json()

    assert (datos["desde"], datos["hasta"]) == ("2026-11-24", "2026-11-24")
    assert [e["numero_pedido"] for e in datos["entregas"]] == ["P-2", "P-1"]  # la más reciente primero
    efectivo = datos["entregas"][1]
    assert efectivo["cliente"] == "Ana Gómez"
    assert efectivo["entrega_barrio"] == "San Fernando"
    assert efectivo["metodo_pago_nombre"] == "Efectivo"
    assert (efectivo["total"], efectivo["monto_recaudado"], efectivo["cambio"]) == ("35000.00", "50000.00", "15000.00")
    tarjeta = datos["entregas"][0]
    assert (tarjeta["monto_recaudado"], tarjeta["cambio"]) == (None, None)
    assert datos["resumen"] == {
        "entregas": 2,
        "pedidos_efectivo": 1,
        "efectivo_cobrado": "35000.00",
        "cambio_entregado": "15000.00",
        "pedidos_en_linea": 1,
        "pagado_en_linea": "20000.00",
    }


def test_filtra_por_fechas_pasadas_segun_el_dia_de_entrega(sede, ana):
    yo = _empleado(REPARTIDOR, "rep@correo.com", sede)
    ayer, antier = HOY - timedelta(days=1), HOY - timedelta(days=2)
    _entrega(sede, yo, ana, "P-1", _hora(ayer, 23), Decimal("10000"))
    _entrega(sede, yo, ana, "P-2", _hora(antier, 9), Decimal("10000"))
    _entrega(sede, yo, ana, "P-3", _hora(HOY, 0), Decimal("10000"))

    solo_ayer = _http(yo).get(URL, {"desde": ayer.isoformat(), "hasta": ayer.isoformat()}).json()
    dos_dias = _http(yo).get(URL, {"desde": antier.isoformat(), "hasta": ayer.isoformat()}).json()

    assert [e["numero_pedido"] for e in solo_ayer["entregas"]] == ["P-1"]
    assert [e["numero_pedido"] for e in dos_dias["entregas"]] == ["P-1", "P-2"]


def test_solo_mis_entregas_y_solo_las_entregadas(sede, ana):
    yo = _empleado(REPARTIDOR, "rep@correo.com", sede)
    otro = _empleado(REPARTIDOR, "otro@correo.com", sede)
    _entrega(sede, yo, ana, "P-1", _hora(HOY, 10), Decimal("10000"))
    _entrega(sede, otro, ana, "P-2", _hora(HOY, 10), Decimal("10000"))
    _entrega(sede, yo, ana, "P-3", None, Decimal("10000"), estado=E.EN_CAMINO)
    _entrega(sede, yo, ana, "P-4", None, Decimal("10000"), estado=E.CANCELADO)

    numeros = [e["numero_pedido"] for e in _http(yo).get(URL).json()["entregas"]]

    assert numeros == ["P-1"]


def test_dia_sin_entregas(sede):
    yo = _empleado(REPARTIDOR, "rep@correo.com", sede)

    datos = _http(yo).get(URL).json()

    assert datos["entregas"] == []
    assert datos["resumen"]["entregas"] == 0 and datos["resumen"]["efectivo_cobrado"] == "0.00"


@pytest.mark.parametrize(
    ("parametros", "campo"),
    [({"desde": "2026-11-24", "hasta": "2026-11-20"}, "desde"), ({"desde": "24/11/2026"}, "desde")],
)
def test_fechas_invalidas(sede, parametros, campo):
    yo = _empleado(REPARTIDOR, "rep@correo.com", sede)

    respuesta = _http(yo).get(URL, parametros)

    assert respuesta.status_code == 400 and campo in respuesta.json()


def test_solo_repartidores(sede):
    operador = _empleado(OPERADOR, "op@correo.com", sede)
    api = APIClient()
    api.force_authenticate(operador.usuario)

    assert api.get(URL).status_code == 403
    assert APIClient().get(URL).status_code == 401
