"""Pruebas de HU-45 · Actualizar el estado de la entrega (SCRUM-82)."""
from decimal import Decimal

import pytest
from django.contrib.auth.models import Group
from rest_framework.test import APIClient

from pedidos.estados import estado_pedido_cambiado
from pedidos.models import EstadoFactura, Factura, HistorialEstadoPedido, MetodoPago, Pedido
from pedidos.models import EstadoPedido as E
from sedes.models import Ciudad, Sede
from usuarios.models import Empleado, Repartidor, Usuario
from usuarios.roles import OPERADOR, REPARTIDOR

pytestmark = pytest.mark.django_db

CLAVE = "ClaveSegura2026"


def url(pedido):
    return f"/api/pedidos/mis-entregas/{pedido.id}/entrega/"


# --- Datos de prueba ------------------------------------------------------------


@pytest.fixture
def centro():
    ciudad = Ciudad.objects.create(nombre="Cali")
    return Sede.objects.create(
        ciudad=ciudad, nombre="Sede Centro", direccion="Calle 1 # 2-3", latitud=3.45,
        longitud=-76.53, barrio="Centro", telefono="3000000000", correo="centro@correo.com",
    )


def crear_personal(rol, email, sede):
    usuario = Usuario.objects.create_user(username=email, email=email, password=CLAVE)
    usuario.groups.add(Group.objects.get_or_create(name=rol)[0])
    empleado = Empleado.objects.create(
        usuario=usuario, sede=sede, tipo_documento="CC", num_documento=email[:10],
        nombres="Nombre", apellidos="Prueba", celular="3001234567", direccion="Calle 4",
    )
    return usuario, empleado


def crear_repartidor(email, sede):
    usuario, empleado = crear_personal(REPARTIDOR, email, sede)
    Repartidor.objects.create(empleado=empleado, disponible=True)
    return usuario


@pytest.fixture
def ana(centro):
    return crear_repartidor("ana@correo.com", centro)


@pytest.fixture
def luis(centro):
    return crear_repartidor("luis@correo.com", centro)


def crear_pedido(sede, repartidor_usuario, estado=E.LISTO_DESPACHO, metodo=MetodoPago.EFECTIVO,
                 estado_factura=EstadoFactura.PENDIENTE):
    pedido = Pedido.objects.create(
        sede=sede, numero_pedido=f"P-{Pedido.objects.count() + 1}", estado=estado,
        repartidor=Repartidor.objects.get(empleado__usuario=repartidor_usuario),
    )
    Factura.objects.create(
        pedido=pedido, numero=f"F-{pedido.id}", subtotal=Decimal("30000"), iva=Decimal("0"),
        costo_domicilio=Decimal("5000"), total=Decimal("35000"), metodo_pago=metodo,
        estado_factura=estado_factura,
    )
    return pedido


def api_de(usuario=None):
    api = APIClient()
    if usuario is not None:
        api.force_authenticate(usuario)
    return api


def avanzar(usuario, pedido, estado, **extra):
    return api_de(usuario).patch(url(pedido), {"estado": estado, **extra}, format="json")


# --- Criterio 1: secuencia estricta Recogido → En camino → Entregado -----------


def test_secuencia_completa_con_tarjeta(ana, centro):
    pedido = crear_pedido(centro, ana, metodo=MetodoPago.TARJETA, estado_factura=EstadoFactura.PAGADA)

    recogido = avanzar(ana, pedido, E.RECOGIDO)
    assert recogido.status_code == 200
    assert recogido.data["estado"] == E.RECOGIDO
    assert recogido.data["siguientes_estados"] == [E.EN_CAMINO]

    assert avanzar(ana, pedido, E.EN_CAMINO).data["estado"] == E.EN_CAMINO
    entregado = avanzar(ana, pedido, E.ENTREGADO)
    assert entregado.status_code == 200
    assert entregado.data["estado"] == E.ENTREGADO
    assert entregado.data["siguientes_estados"] == []

    # Cada paso queda en el historial con el repartidor que lo dio.
    historial = HistorialEstadoPedido.objects.filter(pedido=pedido).order_by("id")
    assert [h.estado for h in historial] == [E.RECOGIDO, E.EN_CAMINO, E.ENTREGADO]
    assert all(h.usuario == ana for h in historial)


@pytest.mark.parametrize(
    "actual,salto",
    [
        (E.LISTO_DESPACHO, E.EN_CAMINO),
        (E.LISTO_DESPACHO, E.ENTREGADO),
        (E.RECOGIDO, E.ENTREGADO),
    ],
)
def test_no_se_pueden_saltar_pasos(ana, centro, actual, salto):
    pedido = crear_pedido(centro, ana, estado=actual, metodo=MetodoPago.TARJETA,
                          estado_factura=EstadoFactura.PAGADA)

    respuesta = avanzar(ana, pedido, salto)

    assert respuesta.status_code == 400
    assert respuesta.data["codigo"] == "paso_no_permitido"
    pedido.refresh_from_db()
    assert pedido.estado == actual


def test_no_se_puede_retroceder(ana, centro):
    pedido = crear_pedido(centro, ana, estado=E.EN_CAMINO)

    assert avanzar(ana, pedido, E.RECOGIDO).status_code == 400


def test_solo_acepta_estados_de_entrega(ana, centro):
    pedido = crear_pedido(centro, ana)

    respuesta = avanzar(ana, pedido, E.CANCELADO)

    assert respuesta.status_code == 400
    assert "estado" in respuesta.data


# --- Criterio 2: registro del recaudo en efectivo y cierre de la orden ---------


def test_entregar_en_efectivo_registra_el_recaudo_y_paga_la_factura(ana, centro):
    pedido = crear_pedido(centro, ana, estado=E.EN_CAMINO)

    respuesta = avanzar(ana, pedido, E.ENTREGADO, monto_recaudado="50000")

    assert respuesta.status_code == 200
    assert respuesta.data["cobrar_en_efectivo"] is False
    factura = Factura.objects.get(pedido=pedido)
    assert factura.estado_factura == EstadoFactura.PAGADA
    assert factura.monto_recaudado == Decimal("50000")
    assert factura.recaudado_por.empleado.usuario == ana
    assert factura.fecha_recaudo is not None


def test_entregar_en_efectivo_sin_monto_responde_400_y_no_cierra(ana, centro):
    pedido = crear_pedido(centro, ana, estado=E.EN_CAMINO)

    respuesta = avanzar(ana, pedido, E.ENTREGADO)

    assert respuesta.status_code == 400
    assert respuesta.data["codigo"] == "monto_obligatorio"
    pedido.refresh_from_db()
    assert pedido.estado == E.EN_CAMINO
    assert Factura.objects.get(pedido=pedido).estado_factura == EstadoFactura.PENDIENTE


def test_monto_menor_al_total_responde_400(ana, centro):
    pedido = crear_pedido(centro, ana, estado=E.EN_CAMINO)

    respuesta = avanzar(ana, pedido, E.ENTREGADO, monto_recaudado="20000")

    assert respuesta.status_code == 400
    assert respuesta.data["codigo"] == "monto_insuficiente"
    pedido.refresh_from_db()
    assert pedido.estado == E.EN_CAMINO


def test_monto_exacto_es_valido(ana, centro):
    pedido = crear_pedido(centro, ana, estado=E.EN_CAMINO)

    assert avanzar(ana, pedido, E.ENTREGADO, monto_recaudado="35000").status_code == 200


def test_con_tarjeta_no_pide_monto_ni_registra_recaudo(ana, centro):
    pedido = crear_pedido(centro, ana, estado=E.EN_CAMINO, metodo=MetodoPago.TARJETA,
                          estado_factura=EstadoFactura.PAGADA)

    respuesta = avanzar(ana, pedido, E.ENTREGADO, monto_recaudado="99999")

    assert respuesta.status_code == 200
    factura = Factura.objects.get(pedido=pedido)
    assert factura.monto_recaudado is None
    assert factura.recaudado_por is None


def test_monto_negativo_responde_400(ana, centro):
    pedido = crear_pedido(centro, ana, estado=E.EN_CAMINO)

    assert avanzar(ana, pedido, E.ENTREGADO, monto_recaudado="-1").status_code == 400


def test_el_endpoint_generico_no_permite_saltarse_el_recaudo(ana, centro):
    pedido = crear_pedido(centro, ana, estado=E.EN_CAMINO)

    respuesta = api_de(ana).patch(
        f"/api/pedidos/{pedido.id}/estado/", {"estado": E.ENTREGADO}, format="json"
    )

    assert respuesta.status_code == 400
    assert respuesta.data["codigo"] == "recaudo_obligatorio"
    pedido.refresh_from_db()
    assert pedido.estado == E.EN_CAMINO


def test_cada_cambio_emite_la_senal_de_tiempo_real(ana, centro, django_capture_on_commit_callbacks):
    pedido = crear_pedido(centro, ana)
    recibidas = []

    def receptor(sender, pedido, estado_anterior, usuario, **kwargs):
        recibidas.append((estado_anterior, pedido.estado))

    estado_pedido_cambiado.connect(receptor)
    try:
        with django_capture_on_commit_callbacks(execute=True):
            avanzar(ana, pedido, E.RECOGIDO)
    finally:
        estado_pedido_cambiado.disconnect(receptor)

    assert recibidas == [(E.LISTO_DESPACHO, E.RECOGIDO)]


# --- Permisos -------------------------------------------------------------------


def test_otro_repartidor_responde_404(ana, luis, centro):
    pedido = crear_pedido(centro, ana)

    assert avanzar(luis, pedido, E.RECOGIDO).status_code == 404


def test_pedido_ya_entregado_responde_404(ana, centro):
    pedido = crear_pedido(centro, ana, estado=E.ENTREGADO, estado_factura=EstadoFactura.PAGADA)

    assert avanzar(ana, pedido, E.ENTREGADO).status_code == 404


def test_otros_roles_responden_403(centro, ana):
    pedido = crear_pedido(centro, ana)
    operador, _ = crear_personal(OPERADOR, "operador@correo.com", centro)

    assert avanzar(operador, pedido, E.RECOGIDO).status_code == 403
    assert api_de().patch(url(pedido), {"estado": E.RECOGIDO}, format="json").status_code == 401
