"""Pruebas de HU-42 · Lista de pedidos asignados (SCRUM-77) y HU-43 · Detalle del pedido asignado."""
from datetime import date
from decimal import Decimal

import pytest
from django.contrib.auth.models import Group
from rest_framework.test import APIClient

from menu.models import Adicion, CategoriaMenu, Insumo, Producto, ProductoTamano
from pedidos.models import DetallePedido, DetallePedidoAdicion, DetallePedidoExclusion
from pedidos.models import EstadoFactura, Factura, MetodoPago, Pedido
from pedidos.models import EstadoPedido as E
from sedes.models import Ciudad, Sede
from usuarios.models import Cliente, Empleado, Repartidor, Usuario
from usuarios.roles import OPERADOR, REPARTIDOR

pytestmark = pytest.mark.django_db

MIS_ENTREGAS = "/api/pedidos/mis-entregas/"
CLAVE = "ClaveSegura2026"


def url_detalle(pedido):
    return f"{MIS_ENTREGAS}{pedido.id}/"


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


@pytest.fixture
def cliente():
    usuario = Usuario.objects.create_user(
        username="cliente@correo.com", email="cliente@correo.com", password=CLAVE
    )
    return Cliente.objects.create(
        usuario=usuario, tipo_documento="CC", num_documento="1000000001", nombres="Laura",
        apellidos="Gómez", celular="3109876543", fecha_nacimiento=date(2000, 1, 1),
    )


def crear_pedido(sede, numero, repartidor_usuario=None, estado=E.LISTO_DESPACHO, **extra):
    repartidor = (
        Repartidor.objects.get(empleado__usuario=repartidor_usuario) if repartidor_usuario else None
    )
    return Pedido.objects.create(
        sede=sede, numero_pedido=numero, estado=estado, repartidor=repartidor,
        entrega_direccion="Carrera 10 # 20-30", entrega_barrio="San Fernando", **extra,
    )


def facturar(pedido, metodo=MetodoPago.EFECTIVO, estado=EstadoFactura.PENDIENTE):
    return Factura.objects.create(
        pedido=pedido, numero=f"F-{pedido.numero_pedido}", subtotal=Decimal("30000"),
        iva=Decimal("0"), costo_domicilio=Decimal("5000"), total=Decimal("35000"),
        metodo_pago=metodo, estado_factura=estado,
    )


def api_de(usuario=None):
    api = APIClient()
    if usuario is not None:
        api.force_authenticate(usuario)
    return api


# --- HU-42, criterio 1: vista privada con los pedidos asignados -----------------


def test_repartidor_ve_solo_sus_pedidos_asignados(ana, luis, centro):
    crear_pedido(centro, "P-ANA", ana)
    crear_pedido(centro, "P-LUIS", luis)
    crear_pedido(centro, "P-SIN-ASIGNAR")

    respuesta = api_de(ana).get(MIS_ENTREGAS)

    assert respuesta.status_code == 200
    assert [p["numero_pedido"] for p in respuesta.data] == ["P-ANA"]


def test_lista_trae_los_datos_de_la_tarjeta(ana, centro, cliente):
    pedido = crear_pedido(centro, "P-1", ana, cliente=cliente)
    facturar(pedido)

    tarjeta = api_de(ana).get(MIS_ENTREGAS).data[0]

    assert tarjeta["estado"] == E.LISTO_DESPACHO
    assert tarjeta["estado_nombre"] == "Listo para despacho"
    assert tarjeta["entrega_barrio"] == "San Fernando"
    assert tarjeta["cliente"] == {"nombre": "Laura Gómez", "celular": "3109876543"}
    assert tarjeta["total"] == "35000.00"
    assert tarjeta["metodo_pago"] == MetodoPago.EFECTIVO
    # El repartidor solo puede dar el siguiente paso de la entrega.
    assert tarjeta["siguientes_estados"] == [E.RECOGIDO]


def test_lista_ordena_del_mas_antiguo_al_mas_nuevo(ana, centro):
    crear_pedido(centro, "P-PRIMERO", ana)
    crear_pedido(centro, "P-SEGUNDO", ana, estado=E.EN_CAMINO)

    numeros = [p["numero_pedido"] for p in api_de(ana).get(MIS_ENTREGAS).data]

    assert numeros == ["P-PRIMERO", "P-SEGUNDO"]


# --- HU-42, criterio 3: el pedido sale de la lista al entregarse ----------------


def test_entregados_y_cancelados_no_aparecen(ana, centro):
    crear_pedido(centro, "P-POR-RECOGER", ana, E.LISTO_DESPACHO)
    crear_pedido(centro, "P-RECOGIDO", ana, E.RECOGIDO)
    crear_pedido(centro, "P-EN-CAMINO", ana, E.EN_CAMINO)
    crear_pedido(centro, "P-ENTREGADO", ana, E.ENTREGADO)
    crear_pedido(centro, "P-CANCELADO", ana, E.CANCELADO)

    numeros = {p["numero_pedido"] for p in api_de(ana).get(MIS_ENTREGAS).data}

    assert numeros == {"P-POR-RECOGER", "P-RECOGIDO", "P-EN-CAMINO"}


def test_sin_pedidos_la_lista_esta_vacia(ana):
    assert api_de(ana).get(MIS_ENTREGAS).data == []


# --- Permisos -------------------------------------------------------------------


def test_sin_sesion_responde_401():
    assert api_de().get(MIS_ENTREGAS).status_code == 401


def test_otros_roles_no_ven_mis_entregas(centro, cliente):
    operador, _ = crear_personal(OPERADOR, "operador@correo.com", centro)

    assert api_de(operador).get(MIS_ENTREGAS).status_code == 403
    assert api_de(cliente.usuario).get(MIS_ENTREGAS).status_code == 403


# --- HU-43: detalle del pedido asignado -----------------------------------------


@pytest.fixture
def pedido_completo(ana, centro, cliente):
    """Pedido con dirección, un plato personalizado y factura."""
    pedido = crear_pedido(
        centro, "P-DETALLE", ana, cliente=cliente, entrega_alias="Casa",
        entrega_indicaciones="Portón negro", entrega_latitud=3.44, entrega_longitud=-76.54,
        descripcion="Llamar al llegar",
    )
    categoria = CategoriaMenu.objects.create(nombre="Hamburguesas")
    hamburguesa = Producto.objects.create(
        categoria=categoria, nombre="Clásica", precio_base=15000, tiempo_preparacion=15
    )
    doble = ProductoTamano.objects.create(producto=hamburguesa, nombre="Doble", precio_adicional=5000)
    queso = Insumo.objects.create(nombre="Queso", unidad_medida="g")
    cebolla = Insumo.objects.create(nombre="Cebolla", unidad_medida="g")
    linea = DetallePedido.objects.create(
        pedido=pedido, producto=hamburguesa, producto_tamano=doble, cantidad=2,
        precio_unitario=15000, subtotal=30000, observaciones="Bien asada",
    )
    DetallePedidoAdicion.objects.create(
        detalle_pedido=linea, adicion=Adicion.objects.create(nombre="Queso extra", precio=3000, insumo=queso),
        cantidad=1, precio_unitario=3000,
    )
    DetallePedidoExclusion.objects.create(detalle_pedido=linea, insumo=cebolla, nombre_insumo="Cebolla")
    return pedido


def test_detalle_muestra_direccion_productos_y_totales(ana, pedido_completo):
    facturar(pedido_completo)

    respuesta = api_de(ana).get(url_detalle(pedido_completo))

    assert respuesta.status_code == 200
    detalle = respuesta.data
    assert detalle["entrega_direccion"] == "Carrera 10 # 20-30"
    assert detalle["entrega_indicaciones"] == "Portón negro"
    assert (detalle["entrega_latitud"], detalle["entrega_longitud"]) == (3.44, -76.54)
    assert detalle["notas"] == "Llamar al llegar"
    assert detalle["subtotal"] == "30000.00"
    assert detalle["costo_domicilio"] == "5000.00"
    assert detalle["total"] == "35000.00"
    [linea] = detalle["lineas"]
    assert linea["nombre"] == "Clásica"
    assert linea["tamano"] == "Doble"
    assert linea["cantidad"] == 2
    assert linea["adiciones"] == [{"nombre": "Queso extra", "cantidad": 1}]
    assert linea["sin"] == ["Cebolla"]
    assert linea["observaciones"] == "Bien asada"


def test_detalle_resalta_el_cobro_en_efectivo(ana, pedido_completo):
    facturar(pedido_completo, MetodoPago.EFECTIVO, EstadoFactura.PENDIENTE)

    detalle = api_de(ana).get(url_detalle(pedido_completo)).data

    assert detalle["metodo_pago"] == MetodoPago.EFECTIVO
    assert detalle["metodo_pago_nombre"] == "Efectivo"
    assert detalle["cobrar_en_efectivo"] is True


@pytest.mark.parametrize(
    "metodo,estado",
    [
        (MetodoPago.TARJETA, EstadoFactura.PAGADA),
        (MetodoPago.TRANSFERENCIA, EstadoFactura.PAGADA),
        (MetodoPago.EFECTIVO, EstadoFactura.PAGADA),
    ],
)
def test_detalle_no_cobra_si_ya_esta_pagado(ana, pedido_completo, metodo, estado):
    facturar(pedido_completo, metodo, estado)

    assert api_de(ana).get(url_detalle(pedido_completo)).data["cobrar_en_efectivo"] is False


def test_detalle_sin_factura_no_falla(ana, pedido_completo):
    detalle = api_de(ana).get(url_detalle(pedido_completo)).data

    assert detalle["total"] is None
    assert detalle["metodo_pago"] is None
    assert detalle["cobrar_en_efectivo"] is False


def test_detalle_de_otro_repartidor_responde_404(luis, pedido_completo):
    assert api_de(luis).get(url_detalle(pedido_completo)).status_code == 404


def test_detalle_de_pedido_entregado_responde_404(ana, pedido_completo):
    Pedido.objects.filter(pk=pedido_completo.pk).update(estado=E.ENTREGADO)

    assert api_de(ana).get(url_detalle(pedido_completo)).status_code == 404
