"""HU-61: automatic block when a sede reaches its capacity."""
from concurrent.futures import ThreadPoolExecutor
from itertools import count
from datetime import date, datetime, time
from decimal import Decimal
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest
from django.contrib.auth.models import Group
from django.db import connection, connections
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APIClient

from menu.models import CategoriaMenu, Producto
from pedidos import capacidad
from pedidos.models import EstadoPedido, Pedido
from sedes.models import CapacidadSede, Ciudad, Sede, ZonaCobertura
from usuarios.models import Cliente, DireccionEntrega, Empleado, Usuario

pytestmark = [pytest.mark.django_db, pytest.mark.capacidad]

CONFIRMAR = "/api/pedidos/confirmar/"
OPERADOR_CREAR = "/api/pedidos/operador/crear/"
CAPACIDAD = "/api/pedidos/capacidad/"
E = EstadoPedido
_folios = count(1)


def _usuario(email, rol=None, sede=None):
    usuario = Usuario.objects.create_user(
        username=email, email=email, password="ClaveSegura2026"
    )
    if rol:
        usuario.groups.add(Group.objects.get_or_create(name=rol)[0])
    if rol and (sede or rol == "administrador"):
        Empleado.objects.create(
            usuario=usuario, sede=sede, tipo_documento="CC", num_documento=email[:10],
            nombres="N", apellidos="A", celular="3001234567", direccion="Calle 4",
        )
    return usuario


def _http(usuario):
    c = APIClient()
    c.force_authenticate(user=usuario)
    return c


def _franja(sede, maximo=2, umbral=1):
    # Every day, the whole day, so the test does not depend on the clock
    return CapacidadSede.objects.create(
        sede=sede, hora_inicio=time(0, 0), hora_fin=time(23, 59, 59),
        dias_semana="lunes,martes,miercoles,jueves,viernes,sabado,domingo",
        max_pedidos_simultaneos=maximo, umbral_alerta=umbral,
    )


def _llenar(sede, cantidad, estado=E.RECIBIDO):
    return [
        Pedido.objects.create(numero_pedido=f"L-{next(_folios)}", sede=sede, estado=estado)
        for _ in range(cantidad)
    ]


@pytest.fixture
def m(db):
    ciudad = Ciudad.objects.create(nombre="Cali")
    sede = Sede.objects.create(
        ciudad=ciudad, nombre="Norte", direccion="Calle 1 # 2-3", latitud=3.45,
        longitud=-76.53, barrio="Granada", telefono="3000000000", correo="s@correo.com",
    )
    otra_sede = Sede.objects.create(
        ciudad=ciudad, nombre="Sur", direccion="Calle 9 # 8-7", latitud=3.40,
        longitud=-76.50, barrio="Tequendama", telefono="3000000001", correo="t@correo.com",
    )
    ZonaCobertura.objects.create(
        sede=sede, nombre="Zona 1", radio=5, centro_latitud=3.45, centro_longitud=-76.53,
        tarifa_domicilio=Decimal("3000"), tiempo_estimado=40, pedido_minimo=Decimal("10000"),
    )
    usuario_cliente = _usuario("cli@correo.com")
    cliente = Cliente.objects.create(
        usuario=usuario_cliente, tipo_documento="CC", num_documento="123", nombres="Ana",
        apellidos="Prueba", celular="3001234567", fecha_nacimiento=date(2000, 1, 1),
    )
    direccion = DireccionEntrega.objects.create(
        ciudad=ciudad, cliente=cliente, direccion="Calle 5 # 6-7", latitud=3.46, longitud=-76.53,
    )
    producto = Producto.objects.create(
        categoria=CategoriaMenu.objects.create(nombre="Platos"), nombre="Hamburguesa",
        precio_base=Decimal("20000"), tiempo_preparacion=15,
    )
    return SimpleNamespace(
        sede=sede, otra_sede=otra_sede, cliente=usuario_cliente, direccion=direccion,
        producto=producto,
        operador=_usuario("op@correo.com", "operador", sede),
        cocina=_usuario("co@correo.com", "cocina", sede),
        admin=_usuario("ad@correo.com", "administrador"),
    )


def _body_cliente(m):
    return {
        "sede_id": m.sede.pk, "direccion_id": m.direccion.pk, "metodo_pago": "tarjeta",
        "items": [{"producto_id": m.producto.pk, "cantidad": 1}],
    }


def _body_operador(m, origen="mostrador", **extra):
    body = {
        "origen": origen, "metodo_pago": "efectivo",
        "items": [{"producto_id": m.producto.pk, "cantidad": 1}], **extra,
    }
    if origen == "telefonico":
        body["direccion_id"] = m.direccion.pk
    return body


# --- Criterio 1: al 100% se bloquea la confirmación informando saturación -------

def test_cliente_bloqueado_al_100(m):
    _franja(m.sede, maximo=2)
    _llenar(m.sede, 2)

    r = _http(m.cliente).post(CONFIRMAR, _body_cliente(m), format="json")

    assert r.status_code == 409
    assert r.data["codigo"] == "capacidad_maxima_alcanzada"
    assert r.data["estado"] == "saturada"
    assert r.data["bloqueado"] is True
    assert "100%" in r.data["detail"] and "2/2" in r.data["detail"]
    assert Pedido.objects.count() == 2


def test_con_cupo_pasa_y_el_ultimo_pedido_cierra_la_sede(m):
    _franja(m.sede, maximo=1)
    c = _http(m.cliente)

    assert c.post(CONFIRMAR, _body_cliente(m), format="json").status_code == 201
    assert c.post(CONFIRMAR, _body_cliente(m), format="json").status_code == 409
    assert Pedido.objects.count() == 1


def test_los_pendientes_de_aprobacion_tambien_ocupan_cupo(m):
    _franja(m.sede, maximo=2)
    _llenar(m.sede, 1, E.RECIBIDO)
    _llenar(m.sede, 1, E.PENDIENTE_APROBACION)

    r = _http(m.cliente).post(CONFIRMAR, _body_cliente(m), format="json")

    assert r.status_code == 409


def test_pedidos_de_otra_sede_o_ya_despachados_no_cuentan(m):
    _franja(m.sede, maximo=2)
    _llenar(m.otra_sede, 5)
    _llenar(m.sede, 3, E.LISTO_DESPACHO)
    _llenar(m.sede, 3, E.CANCELADO)

    r = _http(m.cliente).post(CONFIRMAR, _body_cliente(m), format="json")

    assert r.status_code == 201


# --- Criterio 2: la saturación no frena a cocina -----------------------------

def test_cocina_sigue_procesando_con_la_sede_saturada(m):
    _franja(m.sede, maximo=2)
    pedidos = _llenar(m.sede, 2)
    cocina = _http(m.cocina)

    r = cocina.patch(
        f"/api/pedidos/{pedidos[0].pk}/estado/", {"estado": E.EN_PREPARACION}, format="json"
    )

    assert r.status_code == 200
    assert capacidad.estado_capacidad(m.sede)["estado"] == capacidad.SATURADA


# --- Criterio 3: al listo para despacho o cancelar se libera el cupo -----------

def test_listo_para_despacho_libera_cupo_y_se_reanuda(m):
    _franja(m.sede, maximo=2)
    pedidos = _llenar(m.sede, 2, E.EN_PREPARACION)
    cliente = _http(m.cliente)
    assert cliente.post(CONFIRMAR, _body_cliente(m), format="json").status_code == 409

    r = _http(m.cocina).patch(
        f"/api/pedidos/{pedidos[0].pk}/estado/", {"estado": E.LISTO_DESPACHO}, format="json"
    )
    assert r.status_code == 200

    assert cliente.post(CONFIRMAR, _body_cliente(m), format="json").status_code == 201


def test_cancelar_libera_cupo_y_se_reanuda(m):
    _franja(m.sede, maximo=2)
    pedidos = _llenar(m.sede, 2)
    cliente = _http(m.cliente)
    assert cliente.post(CONFIRMAR, _body_cliente(m), format="json").status_code == 409

    r = _http(m.operador).patch(
        f"/api/pedidos/{pedidos[0].pk}/estado/",
        {"estado": E.CANCELADO, "motivo": "Cliente no contesta"}, format="json",
    )
    assert r.status_code == 200

    assert cliente.post(CONFIRMAR, _body_cliente(m), format="json").status_code == 201


# --- Criterio 4: aplica también al operador telefónico --------------------------

@pytest.mark.parametrize("origen", ["telefonico", "mostrador"])
def test_operador_bloqueado_al_100(m, origen):
    _franja(m.sede, maximo=1)
    _llenar(m.sede, 1)

    r = _http(m.operador).post(OPERADOR_CREAR, _body_operador(m, origen), format="json")

    assert r.status_code == 409
    assert r.data["codigo"] == "capacidad_maxima_alcanzada"
    assert Pedido.objects.count() == 1


def test_operador_con_cupo_crea_el_pedido(m):
    _franja(m.sede, maximo=2)

    r = _http(m.operador).post(OPERADOR_CREAR, _body_operador(m, "telefonico"), format="json")

    assert r.status_code == 201


def test_confirmar_sin_franja_no_salta_la_saturacion(m):
    _franja(m.sede, maximo=1)
    _llenar(m.sede, 1)
    body = _body_operador(m, confirmar_sin_franja=True)

    r = _http(m.operador).post(OPERADOR_CREAR, body, format="json")

    assert r.status_code == 409
    assert r.data["codigo"] == "capacidad_maxima_alcanzada"


# --- Sin franja configurada: se avisa; si no se puede avisar, se rechaza -----------

def test_cliente_sin_franja_es_rechazado(m):
    r = _http(m.cliente).post(CONFIRMAR, _body_cliente(m), format="json")

    assert r.status_code == 409
    assert r.data["codigo"] == "franja_no_configurada"
    assert r.data["requiere_confirmacion"] is False
    assert Pedido.objects.count() == 0


def test_operador_sin_franja_recibe_aviso_y_confirma(m):
    c = _http(m.operador)

    aviso = c.post(OPERADOR_CREAR, _body_operador(m), format="json")
    assert aviso.status_code == 409
    assert aviso.data["codigo"] == "franja_no_configurada"
    assert aviso.data["requiere_confirmacion"] is True
    assert Pedido.objects.count() == 0

    ok = c.post(OPERADOR_CREAR, _body_operador(m, confirmar_sin_franja=True), format="json")
    assert ok.status_code == 201


def test_fuera_de_la_franja_cuenta_como_sin_franja(m):
    ahora = datetime(2026, 11, 9, 20, 0, tzinfo=ZoneInfo("America/Bogota"))  # a Monday
    CapacidadSede.objects.create(
        sede=m.sede, hora_inicio=time(11, 0), hora_fin=time(15, 0), dias_semana="lunes",
        max_pedidos_simultaneos=5, umbral_alerta=3,
    )

    assert capacidad.franja_actual(m.sede, ahora) is None
    assert capacidad.estado_capacidad(m.sede, ahora=ahora)["estado"] == capacidad.SIN_FRANJA


def test_franja_actual_respeta_dia_y_hora(m):
    franja = CapacidadSede.objects.create(
        sede=m.sede, hora_inicio=time(11, 0), hora_fin=time(15, 0),
        dias_semana="lunes, martes", max_pedidos_simultaneos=5, umbral_alerta=3,
    )
    tz = ZoneInfo("America/Bogota")

    assert capacidad.franja_actual(m.sede, datetime(2026, 11, 9, 12, 0, tzinfo=tz)) == franja
    assert capacidad.franja_actual(m.sede, datetime(2026, 11, 10, 12, 0, tzinfo=tz)) == franja
    assert capacidad.franja_actual(m.sede, datetime(2026, 11, 11, 12, 0, tzinfo=tz)) is None


# --- Endpoint de estado, para deshabilitar el botón de antemano -------------------

def test_endpoint_cliente_disponible_y_saturada(m):
    _franja(m.sede, maximo=2, umbral=1)
    c = _http(m.cliente)

    r = c.get(CAPACIDAD, {"sede": m.sede.pk})
    assert r.status_code == 200
    assert (r.data["estado"], r.data["bloqueado"], r.data["activos"], r.data["maximo"]) == (
        "disponible", False, 0, 2,
    )

    _llenar(m.sede, 2)
    r = c.get(CAPACIDAD, {"sede": m.sede.pk})
    assert (r.data["estado"], r.data["bloqueado"], r.data["porcentaje"]) == ("saturada", True, 100)
    assert r.data["en_alerta"] is True


def test_endpoint_sin_franja_cliente_bloqueado_y_operador_con_aviso(m):
    cliente = _http(m.cliente).get(CAPACIDAD, {"sede": m.sede.pk})
    operador = _http(m.operador).get(CAPACIDAD)

    assert cliente.data["estado"] == operador.data["estado"] == "sin_franja"
    assert cliente.data["bloqueado"] is True and cliente.data["requiere_confirmacion"] is False
    assert operador.data["bloqueado"] is False and operador.data["requiere_confirmacion"] is True


def test_endpoint_operador_solo_ve_su_sede(m):
    _franja(m.sede, maximo=3)
    _franja(m.otra_sede, maximo=9)

    r = _http(m.operador).get(CAPACIDAD, {"sede": m.otra_sede.pk})

    assert r.data["sede"] == m.sede.pk and r.data["maximo"] == 3


def test_endpoint_permisos_y_parametros(m):
    assert APIClient().get(CAPACIDAD, {"sede": m.sede.pk}).status_code == 401
    assert _http(m.cocina).get(CAPACIDAD, {"sede": m.sede.pk}).status_code == 403
    assert _http(m.cliente).get(CAPACIDAD).status_code == 400
    assert _http(m.cliente).get(CAPACIDAD, {"sede": 99999}).status_code == 404
    assert _http(m.admin).get(CAPACIDAD, {"sede": m.sede.pk}).status_code == 200


# --- Concurrencia -------------------------------------------------------------------

def test_el_chequeo_bloquea_la_fila_de_la_sede(m):
    _franja(m.sede, maximo=5)

    with CaptureQueriesContext(connection) as consultas:
        capacidad.validar_cupo_nuevo_pedido(m.sede)

    assert any("FOR UPDATE" in q["sql"] for q in consultas)


@pytest.mark.django_db(transaction=True)
def test_pedidos_simultaneos_no_superan_el_cupo(m):
    _franja(m.sede, maximo=2)
    # one customer per thread, all fighting for the last slots
    clientes = []
    for i in range(6):
        u = _usuario(f"c{i}@correo.com")
        cli = Cliente.objects.create(
            usuario=u, tipo_documento="CC", num_documento=f"9{i}", nombres="A",
            apellidos="B", celular=f"30000000{i:02d}", fecha_nacimiento=date(2000, 1, 1),
        )
        d = DireccionEntrega.objects.create(
            ciudad=m.sede.ciudad, cliente=cli, direccion="Calle 5", latitud=3.46, longitud=-76.53,
        )
        clientes.append((u, d))

    def pedir(par):
        usuario, direccion = par
        try:
            body = {
                "sede_id": m.sede.pk, "direccion_id": direccion.pk, "metodo_pago": "tarjeta",
                "items": [{"producto_id": m.producto.pk, "cantidad": 1}],
            }
            return _http(usuario).post(CONFIRMAR, body, format="json").status_code
        finally:
            connections.close_all()

    with ThreadPoolExecutor(max_workers=6) as pool:
        codigos = list(pool.map(pedir, clientes))

    assert codigos.count(201) == 2
    assert codigos.count(409) == 4
    assert Pedido.objects.filter(sede=m.sede).count() == 2
