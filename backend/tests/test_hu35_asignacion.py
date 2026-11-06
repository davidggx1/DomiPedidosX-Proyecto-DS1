"""Pruebas de HU-35 · Asignación manual de repartidor (SCRUM-71)."""
import pytest
from django.contrib.auth.models import Group
from rest_framework.test import APIClient

from pedidos.asignacion import asignacion_cambiada, repartidor_libre
from pedidos.models import EstadoPedido as E
from pedidos.models import OrigenPedido, Pedido
from sedes.models import Ciudad, Sede
from usuarios.models import Empleado, Repartidor, Usuario
from usuarios.roles import ADMINISTRADOR, COCINA, OPERADOR, REPARTIDOR

pytestmark = pytest.mark.django_db

DESPACHO = "/api/pedidos/despacho/"
REPARTIDORES = "/api/usuarios/repartidores/"
CLAVE = "ClaveSegura2026"


def url(pedido):
    return f"/api/pedidos/{pedido.id}/repartidor/"


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


def crear_personal(rol, email, sede=None, activo=True, nombre="Nombre"):
    usuario = Usuario.objects.create_user(
        username=email, email=email, password=CLAVE, is_active=activo
    )
    usuario.groups.add(Group.objects.get_or_create(name=rol)[0])
    empleado = None
    if sede is not None:
        empleado = Empleado.objects.create(
            usuario=usuario, sede=sede, tipo_documento="CC", num_documento=email[:10],
            nombres=nombre, apellidos="Prueba", celular="3001234567", direccion="Calle 4",
        )
    return usuario, empleado


def crear_repartidor(email, sede, disponible=True, activo=True, nombre="Ana"):
    usuario, empleado = crear_personal(REPARTIDOR, email, sede, activo, nombre)
    return Repartidor.objects.create(empleado=empleado, disponible=disponible)


def crear_pedido(sede, numero="P-1", estado=E.LISTO_DESPACHO, **extra):
    return Pedido.objects.create(sede=sede, numero_pedido=numero, estado=estado, **extra)


def api_de(usuario=None):
    api = APIClient()
    if usuario is not None:
        api.force_authenticate(usuario)
    return api


@pytest.fixture
def operador(centro):
    return crear_personal(OPERADOR, "operador@correo.com", centro)[0]


@pytest.fixture
def ana(centro):
    return crear_repartidor("ana@correo.com", centro)


# --- Criterio 1: el operador ve pedidos listos y repartidores disponibles ---------


def test_operador_ve_pedidos_listos_para_despacho(operador, centro):
    crear_pedido(centro, "P-LISTO")
    crear_pedido(centro, "P-COCINA", E.EN_PREPARACION)
    crear_pedido(centro, "P-MOSTRADOR", origen=OrigenPedido.MOSTRADOR)

    respuesta = api_de(operador).get(DESPACHO)

    assert respuesta.status_code == 200
    assert [p["numero_pedido"] for p in respuesta.data] == ["P-LISTO"]
    assert respuesta.data[0]["repartidor"] is None


def test_despacho_solo_muestra_la_sede_del_operador(operador, centro, sur):
    crear_pedido(centro, "P-CENTRO")
    crear_pedido(sur, "P-SUR")

    assert [p["numero_pedido"] for p in api_de(operador).get(DESPACHO).data] == ["P-CENTRO"]


def test_administrador_ve_todas_las_sedes_y_filtra(centro, sur):
    admin, _ = crear_personal(ADMINISTRADOR, "admin@correo.com")
    crear_pedido(centro, "P-CENTRO")
    crear_pedido(sur, "P-SUR")
    api = api_de(admin)

    assert {p["numero_pedido"] for p in api.get(DESPACHO).data} == {"P-CENTRO", "P-SUR"}
    assert [p["numero_pedido"] for p in api.get(DESPACHO, {"sede": sur.id}).data] == ["P-SUR"]


def test_lista_de_repartidores_marca_al_ocupado(operador, centro, ana):
    crear_pedido(centro, "P-1", E.EN_CAMINO, repartidor=ana)
    crear_repartidor("beto@correo.com", centro, nombre="Beto")

    datos = {r["nombres"]: r for r in api_de(operador).get(REPARTIDORES, {"disponible": "true"}).data}

    assert datos["Ana"]["pedidos_activos"] == 1
    assert datos["Beto"]["pedidos_activos"] == 0


# --- Criterio 2: vincular pedido y repartidor -----------------------------------


def test_operador_asigna_repartidor_disponible(operador, centro, ana):
    pedido = crear_pedido(centro)

    respuesta = api_de(operador).post(url(pedido), {"repartidor": ana.id}, format="json")

    assert respuesta.status_code == 200
    assert respuesta.data["repartidor"] == {"id": ana.id, "nombre": "Ana Prueba"}
    pedido.refresh_from_db()
    assert pedido.repartidor_id == ana.id


def test_el_repartidor_ve_el_pedido_asignado(operador, centro, ana):
    pedido = crear_pedido(centro)
    api_de(operador).post(url(pedido), {"repartidor": ana.id}, format="json")

    respuesta = api_de(ana.empleado.usuario).get(f"/api/pedidos/{pedido.id}/estado/")

    assert respuesta.status_code == 200
    assert respuesta.data["siguientes_estados"] == [E.RECOGIDO]


def test_asignar_envia_senal_para_tiempo_real(operador, centro, ana, django_capture_on_commit_callbacks):
    pedido = crear_pedido(centro)
    recibidas = []

    def receptor(sender, pedido, repartidor, usuario, **kwargs):
        recibidas.append((pedido.id, repartidor.id if repartidor else None))

    asignacion_cambiada.connect(receptor)
    try:
        with django_capture_on_commit_callbacks(execute=True):
            api_de(operador).post(url(pedido), {"repartidor": ana.id}, format="json")
    finally:
        asignacion_cambiada.disconnect(receptor)

    assert recibidas == [(pedido.id, ana.id)]


# --- Criterio 3: no se asigna a quien no está disponible u ocupado ----------------


def test_no_se_asigna_a_repartidor_no_disponible(operador, centro):
    ocupado = crear_repartidor("ana@correo.com", centro, disponible=False)
    pedido = crear_pedido(centro)

    respuesta = api_de(operador).post(url(pedido), {"repartidor": ocupado.id}, format="json")

    assert respuesta.status_code == 400
    assert respuesta.data["codigo"] == "repartidor_no_disponible"
    pedido.refresh_from_db()
    assert pedido.repartidor_id is None


def test_no_se_asigna_a_repartidor_con_otra_entrega(operador, centro, ana):
    crear_pedido(centro, "P-EN-CAMINO", E.EN_CAMINO, repartidor=ana)
    pedido = crear_pedido(centro, "P-NUEVO")

    respuesta = api_de(operador).post(url(pedido), {"repartidor": ana.id}, format="json")

    assert respuesta.status_code == 400
    assert respuesta.data["codigo"] == "repartidor_ocupado"


def test_repartidor_queda_libre_al_entregar(centro, ana):
    crear_pedido(centro, "P-ENTREGADO", E.ENTREGADO, repartidor=ana)

    assert repartidor_libre(ana) is True


def test_no_se_asigna_a_repartidor_de_otra_sede(operador, centro, sur):
    de_sur = crear_repartidor("beto@correo.com", sur)
    pedido = crear_pedido(centro)

    respuesta = api_de(operador).post(url(pedido), {"repartidor": de_sur.id}, format="json")

    assert respuesta.status_code == 400
    assert respuesta.data["codigo"] == "otra_sede"


def test_no_se_asigna_a_cuenta_desactivada(operador, centro):
    inactivo = crear_repartidor("ana@correo.com", centro, activo=False)
    pedido = crear_pedido(centro)

    respuesta = api_de(operador).post(url(pedido), {"repartidor": inactivo.id}, format="json")

    assert respuesta.status_code == 400
    assert respuesta.data["codigo"] == "repartidor_inactivo"


@pytest.mark.parametrize("estado", [E.RECIBIDO, E.EN_PREPARACION, E.EN_CAMINO, E.ENTREGADO])
def test_solo_se_asignan_pedidos_listos(operador, centro, ana, estado):
    pedido = crear_pedido(centro, estado=estado)

    respuesta = api_de(operador).post(url(pedido), {"repartidor": ana.id}, format="json")

    assert respuesta.status_code == 400
    assert respuesta.data["codigo"] == "pedido_no_listo"


def test_pedido_de_mostrador_no_lleva_repartidor(operador, centro, ana):
    pedido = crear_pedido(centro, origen=OrigenPedido.MOSTRADOR)

    respuesta = api_de(operador).post(url(pedido), {"repartidor": ana.id}, format="json")

    assert respuesta.status_code == 400
    assert respuesta.data["codigo"] == "pedido_sin_domicilio"


def test_repartidor_inexistente_o_invalido(operador, centro):
    pedido = crear_pedido(centro)
    api = api_de(operador)

    assert api.post(url(pedido), {"repartidor": 9999}, format="json").status_code == 400
    assert api.post(url(pedido), {}, format="json").status_code == 400
    assert api.post(url(pedido), {"repartidor": "abc"}, format="json").status_code == 400


# --- Criterio 4: un solo repartidor; para cambiarlo, primero se retira -----------


def test_no_se_reemplaza_sin_retirar_primero(operador, centro, ana):
    beto = crear_repartidor("beto@correo.com", centro, nombre="Beto")
    pedido = crear_pedido(centro, repartidor=ana)

    respuesta = api_de(operador).post(url(pedido), {"repartidor": beto.id}, format="json")

    assert respuesta.status_code == 409
    assert respuesta.data["codigo"] == "pedido_ya_asignado"
    pedido.refresh_from_db()
    assert pedido.repartidor_id == ana.id


def test_retirar_y_asignar_otro(operador, centro, ana):
    beto = crear_repartidor("beto@correo.com", centro, nombre="Beto")
    pedido = crear_pedido(centro, repartidor=ana)
    api = api_de(operador)

    retiro = api.delete(url(pedido))
    assert retiro.status_code == 200
    assert retiro.data["repartidor"] is None

    nueva = api.post(url(pedido), {"repartidor": beto.id}, format="json")
    assert nueva.status_code == 200
    assert nueva.data["repartidor"]["id"] == beto.id


def test_no_se_retira_si_ya_lo_recogio(operador, centro, ana):
    pedido = crear_pedido(centro, estado=E.RECOGIDO, repartidor=ana)

    respuesta = api_de(operador).delete(url(pedido))

    assert respuesta.status_code == 400
    assert respuesta.data["codigo"] == "pedido_recogido"


def test_retirar_sin_asignacion_responde_400(operador, centro):
    respuesta = api_de(operador).delete(url(crear_pedido(centro)))

    assert respuesta.status_code == 400
    assert respuesta.data["codigo"] == "sin_asignacion"


# --- Permisos ----------------------------------------------------------------------


def test_sin_sesion_responde_401(centro):
    pedido = crear_pedido(centro)

    assert api_de().get(DESPACHO).status_code == 401
    assert api_de().post(url(pedido), {"repartidor": 1}, format="json").status_code == 401


@pytest.mark.parametrize("rol", [COCINA, REPARTIDOR])
def test_cocina_y_repartidor_no_asignan(centro, ana, rol):
    usuario, _ = crear_personal(rol, f"{rol}x@correo.com", centro)
    pedido = crear_pedido(centro)

    assert api_de(usuario).get(DESPACHO).status_code == 403
    assert api_de(usuario).post(url(pedido), {"repartidor": ana.id}, format="json").status_code == 403


def test_operador_no_asigna_pedidos_de_otra_sede(operador, sur):
    de_sur = crear_repartidor("beto@correo.com", sur)
    pedido = crear_pedido(sur, "P-SUR")

    respuesta = api_de(operador).post(url(pedido), {"repartidor": de_sur.id}, format="json")

    assert respuesta.status_code == 404
