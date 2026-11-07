"""Pruebas del tablero de cocina (HU-29, SCRUM-63) y la comanda (HU-30, SCRUM-64)."""
from datetime import timedelta
from decimal import Decimal

import pytest
from django.contrib.auth.models import Group
from django.db import IntegrityError
from django.utils import timezone
from rest_framework.test import APIClient

from menu.models import Adicion, CategoriaMenu, Insumo, Producto, ProductoTamano
from pedidos.estados import cambiar_estado
from pedidos.models import DetallePedido, DetallePedidoAdicion, DetallePedidoExclusion
from pedidos.models import EstadoPedido as E
from pedidos.models import HistorialEstadoPedido, Pedido
from sedes.models import Ciudad, Sede
from usuarios.models import Empleado, Usuario
from usuarios.roles import ADMINISTRADOR, COCINA, OPERADOR, REPARTIDOR

pytestmark = pytest.mark.django_db

TABLERO = "/api/pedidos/cocina/tablero/"
CLAVE = "ClaveSegura2026"


def url_comanda(pedido):
    return f"/api/pedidos/{pedido.id}/cocina/"


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
def cocina(centro):
    return crear_personal(COCINA, "cocina@correo.com", centro)


def api_de(usuario=None):
    api = APIClient()
    if usuario is not None:
        api.force_authenticate(usuario)
    return api


@pytest.fixture
def menu():
    categoria = CategoriaMenu.objects.create(nombre="Hamburguesas")
    hamburguesa = Producto.objects.create(
        categoria=categoria, nombre="Clásica", precio_base=15000, tiempo_preparacion=15
    )
    queso = Insumo.objects.create(nombre="Queso", unidad_medida="g")
    cebolla = Insumo.objects.create(nombre="Cebolla", unidad_medida="g")
    return {
        "hamburguesa": hamburguesa,
        "doble": ProductoTamano.objects.create(producto=hamburguesa, nombre="Doble", precio_adicional=5000),
        "queso_extra": Adicion.objects.create(nombre="Queso extra", precio=3000, insumo=queso),
        "cebolla": cebolla,
    }


def crear_pedido(sede, numero, estado=E.RECIBIDO, notas=""):
    return Pedido.objects.create(sede=sede, numero_pedido=numero, estado=estado, descripcion=notas)


def agregar_plato(pedido, producto, cantidad=1, tamano=None, observaciones=""):
    return DetallePedido.objects.create(
        pedido=pedido, producto=producto, producto_tamano=tamano, cantidad=cantidad,
        precio_unitario=15000, subtotal=15000 * cantidad, observaciones=observaciones,
    )


def marcar_recibido(pedido, hace_minutos):
    """Simula que el pedido entró a cocina hace `hace_minutos` minutos."""
    registro = HistorialEstadoPedido.objects.create(pedido=pedido, estado=E.RECIBIDO)
    HistorialEstadoPedido.objects.filter(pk=registro.pk).update(
        fecha_hora=timezone.now() - timedelta(minutes=hace_minutos)
    )


# --- HU-29: tablero Kanban ---------------------------------------------------------


def test_tablero_tiene_las_tres_columnas_de_cocina(cocina, centro):
    for numero, estado in [("P-1", E.RECIBIDO), ("P-2", E.EN_PREPARACION), ("P-3", E.LISTO_DESPACHO)]:
        crear_pedido(centro, numero, estado)
    # Estos no son de cocina y no deben aparecer.
    crear_pedido(centro, "P-4", E.PENDIENTE_APROBACION)
    crear_pedido(centro, "P-5", E.EN_CAMINO)

    respuesta = api_de(cocina).get(TABLERO)

    assert respuesta.status_code == 200
    assert list(respuesta.data) == [E.RECIBIDO, E.EN_PREPARACION, E.LISTO_DESPACHO]
    assert [t["numero_pedido"] for t in respuesta.data[E.RECIBIDO]] == ["P-1"]
    assert [t["numero_pedido"] for t in respuesta.data[E.EN_PREPARACION]] == ["P-2"]
    assert [t["numero_pedido"] for t in respuesta.data[E.LISTO_DESPACHO]] == ["P-3"]


def test_tarjeta_muestra_numero_resumen_y_hora(cocina, centro, menu):
    pedido = crear_pedido(centro, "P-1")
    agregar_plato(pedido, menu["hamburguesa"], cantidad=2, tamano=menu["doble"])

    tarjeta = api_de(cocina).get(TABLERO).data[E.RECIBIDO][0]

    assert tarjeta["numero_pedido"] == "P-1"
    assert tarjeta["resumen"] == ["2x Clásica (Doble)"]
    assert tarjeta["recibido_en"] is not None
    assert tarjeta["listo_en"] is None
    assert tarjeta["siguientes_estados"] == [E.EN_PREPARACION, E.CANCELADO]


def test_pedidos_mas_antiguos_primero(cocina, centro):
    nuevo = crear_pedido(centro, "P-NUEVO")
    viejo = crear_pedido(centro, "P-VIEJO")
    marcar_recibido(nuevo, hace_minutos=2)
    marcar_recibido(viejo, hace_minutos=20)

    columna = api_de(cocina).get(TABLERO).data[E.RECIBIDO]

    assert [t["numero_pedido"] for t in columna] == ["P-VIEJO", "P-NUEVO"]


def test_pedido_aprobado_entra_a_recibido(cocina, centro):
    operador = crear_personal(OPERADOR, "operador@correo.com", centro)
    pedido = crear_pedido(centro, "P-1", E.PENDIENTE_APROBACION)
    api = api_de(cocina)
    assert api.get(TABLERO).data[E.RECIBIDO] == []

    cambiar_estado(pedido, E.RECIBIDO, usuario=operador, rol=OPERADOR)

    assert [t["numero_pedido"] for t in api.get(TABLERO).data[E.RECIBIDO]] == ["P-1"]


def test_tarjeta_avanza_de_columna_y_guarda_la_hora_de_listo(cocina, centro):
    pedido = crear_pedido(centro, "P-1")
    api = api_de(cocina)

    api.patch(f"/api/pedidos/{pedido.id}/estado/", {"estado": E.EN_PREPARACION}, format="json")
    api.patch(f"/api/pedidos/{pedido.id}/estado/", {"estado": E.LISTO_DESPACHO}, format="json")
    tablero = api.get(TABLERO).data

    assert tablero[E.RECIBIDO] == []
    assert tablero[E.LISTO_DESPACHO][0]["listo_en"] is not None


def test_cocina_solo_ve_su_sede(cocina, centro, sur):
    crear_pedido(centro, "P-CENTRO")
    crear_pedido(sur, "P-SUR")

    columna = api_de(cocina).get(TABLERO).data[E.RECIBIDO]

    assert [t["numero_pedido"] for t in columna] == ["P-CENTRO"]


def test_administrador_filtra_por_sede(centro, sur):
    admin = crear_personal(ADMINISTRADOR, "admin@correo.com")
    crear_pedido(centro, "P-CENTRO")
    crear_pedido(sur, "P-SUR")
    api = api_de(admin)

    todos = api.get(TABLERO).data[E.RECIBIDO]
    solo_sur = api.get(TABLERO, {"sede": sur.id}).data[E.RECIBIDO]

    assert {t["numero_pedido"] for t in todos} == {"P-CENTRO", "P-SUR"}
    assert [t["numero_pedido"] for t in solo_sur] == ["P-SUR"]
    assert api.get(TABLERO, {"sede": "abc"}).status_code == 400


def test_tarjeta_avisa_si_hay_notas_o_cambios(cocina, centro, menu):
    simple = crear_pedido(centro, "P-SIMPLE")
    agregar_plato(simple, menu["hamburguesa"])
    especial = crear_pedido(centro, "P-ESPECIAL", notas="Tocar el timbre")
    plato = agregar_plato(especial, menu["hamburguesa"])
    DetallePedidoExclusion.objects.create(detalle_pedido=plato, insumo=menu["cebolla"], nombre_insumo="Cebolla")

    tarjetas = {t["numero_pedido"]: t for t in api_de(cocina).get(TABLERO).data[E.RECIBIDO]}

    assert (tarjetas["P-SIMPLE"]["tiene_notas"], tarjetas["P-SIMPLE"]["tiene_cambios"]) == (False, False)
    assert (tarjetas["P-ESPECIAL"]["tiene_notas"], tarjetas["P-ESPECIAL"]["tiene_cambios"]) == (True, True)


# --- HU-30: comanda ------------------------------------------------------------------


def test_comanda_muestra_platos_tamanos_adiciones_quitados_y_notas(cocina, centro, menu):
    pedido = crear_pedido(centro, "P-1", notas="Cliente alérgico al maní")
    plato = agregar_plato(
        pedido, menu["hamburguesa"], cantidad=2, tamano=menu["doble"], observaciones="Bien asada"
    )
    DetallePedidoAdicion.objects.create(
        detalle_pedido=plato, adicion=menu["queso_extra"], cantidad=1, precio_unitario=3000
    )
    DetallePedidoExclusion.objects.create(detalle_pedido=plato, insumo=menu["cebolla"], nombre_insumo="Cebolla")

    respuesta = api_de(cocina).get(url_comanda(pedido))

    assert respuesta.status_code == 200
    assert respuesta.data["notas"] == "Cliente alérgico al maní"
    linea = respuesta.data["lineas"][0]
    assert linea["nombre"] == "Clásica"
    assert linea["tamano"] == "Doble"
    assert linea["cantidad"] == 2
    assert linea["adiciones"] == [{"nombre": "Queso extra", "cantidad": 1}]
    assert linea["sin"] == ["Cebolla"]
    assert linea["observaciones"] == "Bien asada"


def test_comanda_conserva_el_nombre_aunque_renombren_el_insumo(cocina, centro, menu):
    pedido = crear_pedido(centro, "P-1")
    plato = agregar_plato(pedido, menu["hamburguesa"])
    DetallePedidoExclusion.objects.create(detalle_pedido=plato, insumo=menu["cebolla"], nombre_insumo="Cebolla")
    Insumo.objects.filter(pk=menu["cebolla"].pk).update(nombre="Cebolla morada")

    linea = api_de(cocina).get(url_comanda(pedido)).data["lineas"][0]

    assert linea["sin"] == ["Cebolla"]


def test_plato_sin_cambios_no_tiene_adiciones_ni_quitados(cocina, centro, menu):
    pedido = crear_pedido(centro, "P-1")
    agregar_plato(pedido, menu["hamburguesa"])

    linea = api_de(cocina).get(url_comanda(pedido)).data["lineas"][0]

    assert (linea["tamano"], linea["adiciones"], linea["sin"]) == (None, [], [])


def test_no_se_repite_un_ingrediente_quitado_en_el_mismo_plato(centro, menu):
    plato = agregar_plato(crear_pedido(centro, "P-1"), menu["hamburguesa"])
    DetallePedidoExclusion.objects.create(detalle_pedido=plato, insumo=menu["cebolla"], nombre_insumo="Cebolla")

    with pytest.raises(IntegrityError):
        DetallePedidoExclusion.objects.create(
            detalle_pedido=plato, insumo=menu["cebolla"], nombre_insumo="Cebolla"
        )


def test_comanda_de_otra_sede_responde_404(cocina, sur):
    assert api_de(cocina).get(url_comanda(crear_pedido(sur, "P-SUR"))).status_code == 404


# --- Permisos ------------------------------------------------------------------------


def test_sin_sesion_responde_401(centro):
    assert api_de().get(TABLERO).status_code == 401
    assert api_de().get(url_comanda(crear_pedido(centro, "P-1"))).status_code == 401


def test_operador_ve_el_tablero_de_su_sede(centro):
    operador = crear_personal(OPERADOR, "operador@correo.com", centro)
    crear_pedido(centro, "P-1")

    respuesta = api_de(operador).get(TABLERO)

    assert respuesta.status_code == 200
    # El operador ve la tarjeta, pero no puede mover pedidos en cocina.
    assert respuesta.data[E.RECIBIDO][0]["siguientes_estados"] == [E.CANCELADO]


def test_repartidor_no_ve_la_cocina(centro):
    repartidor = crear_personal(REPARTIDOR, "repa@correo.com", centro)
    pedido = crear_pedido(centro, "P-1")

    assert api_de(repartidor).get(TABLERO).status_code == 403
    assert api_de(repartidor).get(url_comanda(pedido)).status_code == 403


def test_precio_de_la_adicion_no_cambia_la_comanda(cocina, centro, menu):
    pedido = crear_pedido(centro, "P-1")
    plato = agregar_plato(pedido, menu["hamburguesa"])
    DetallePedidoAdicion.objects.create(
        detalle_pedido=plato, adicion=menu["queso_extra"], cantidad=2, precio_unitario=Decimal("3000")
    )

    linea = api_de(cocina).get(url_comanda(pedido)).data["lineas"][0]

    assert linea["adiciones"] == [{"nombre": "Queso extra", "cantidad": 2}]
