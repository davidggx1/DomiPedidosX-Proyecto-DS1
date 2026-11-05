"""Pruebas de HU-31 · Cambiar el estado desde cocina y máquina de estados (SCRUM-68)."""
import pytest
from django.contrib.auth.models import Group
from rest_framework.test import APIClient

from pedidos.estados import (
    TRANSICIONES,
    TransicionInvalida,
    cambiar_estado,
    estado_pedido_cambiado,
    registrar_estado_inicial,
    siguientes_estados,
    validar_transicion,
)
from pedidos.models import EstadoPedido as E
from pedidos.models import HistorialEstadoPedido, Pedido
from sedes.models import Ciudad, Sede
from usuarios.models import Cliente, Empleado, Repartidor, Usuario
from usuarios.roles import ADMINISTRADOR, COCINA, OPERADOR, REPARTIDOR

pytestmark = pytest.mark.django_db

CLAVE = "ClaveSegura2026"


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
    empleado = None
    if sede is not None:
        empleado = Empleado.objects.create(
            usuario=usuario, sede=sede, tipo_documento="CC", num_documento=email[:10],
            nombres="Nombre", apellidos="Prueba", celular="3001234567", direccion="Calle 4",
        )
    return usuario, empleado


def crear_cliente(email, celular):
    usuario = Usuario.objects.create_user(username=email, email=email, password=CLAVE)
    perfil = Cliente.objects.create(
        usuario=usuario, tipo_documento="CC", num_documento=celular, nombres="Ana",
        apellidos="Pérez", celular=celular, fecha_nacimiento="2000-01-01",
    )
    return usuario, perfil


def crear_pedido(sede, estado=E.RECIBIDO, numero="P-1", **extra):
    return Pedido.objects.create(sede=sede, numero_pedido=numero, estado=estado, **extra)


def url(pedido):
    return f"/api/pedidos/{pedido.id}/estado/"


def api_de(usuario=None):
    api = APIClient()
    if usuario is not None:
        api.force_authenticate(usuario)
    return api


@pytest.fixture
def cocina(centro):
    return crear_personal(COCINA, "cocina@correo.com", centro)[0]


@pytest.fixture
def operador(centro):
    return crear_personal(OPERADOR, "operador@correo.com", centro)[0]


# --- Criterio 1 y 2: cocina avanza el pedido paso a paso --------------------------


def test_cocina_pasa_de_recibido_a_en_preparacion(cocina, centro):
    pedido = crear_pedido(centro)

    respuesta = api_de(cocina).patch(url(pedido), {"estado": E.EN_PREPARACION}, format="json")

    assert respuesta.status_code == 200
    assert respuesta.data["estado"] == E.EN_PREPARACION
    assert respuesta.data["estado_nombre"] == "En preparación"
    assert respuesta.data["siguientes_estados"] == [E.LISTO_DESPACHO, E.CANCELADO]
    pedido.refresh_from_db()
    assert pedido.estado == E.EN_PREPARACION


def test_cocina_termina_su_ciclo_en_listo_para_despacho(cocina, centro):
    pedido = crear_pedido(centro, E.EN_PREPARACION)

    respuesta = api_de(cocina).patch(url(pedido), {"estado": E.LISTO_DESPACHO}, format="json")

    assert respuesta.status_code == 200
    assert respuesta.data["estado"] == E.LISTO_DESPACHO
    # Desde aquí cocina ya no puede mover el pedido: sigue la asignación (HU-35).
    assert respuesta.data["siguientes_estados"] == []


# --- Criterio 3: no se saltan pasos ni se retrocede --------------------------------


def test_no_se_puede_saltar_de_recibido_a_listo(cocina, centro):
    pedido = crear_pedido(centro)

    respuesta = api_de(cocina).patch(url(pedido), {"estado": E.LISTO_DESPACHO}, format="json")

    assert respuesta.status_code == 400
    assert respuesta.data["codigo"] == "paso_no_permitido"
    pedido.refresh_from_db()
    assert pedido.estado == E.RECIBIDO


def test_no_se_puede_retroceder(cocina, centro):
    pedido = crear_pedido(centro, E.EN_PREPARACION)

    respuesta = api_de(cocina).patch(url(pedido), {"estado": E.RECIBIDO}, format="json")

    assert respuesta.status_code == 400
    assert respuesta.data["codigo"] == "paso_no_permitido"


def test_no_se_cambia_a_un_estado_igual(cocina, centro):
    pedido = crear_pedido(centro)

    respuesta = api_de(cocina).patch(url(pedido), {"estado": E.RECIBIDO}, format="json")

    assert respuesta.status_code == 400
    assert respuesta.data["codigo"] == "mismo_estado"


@pytest.mark.parametrize("final", [E.ENTREGADO, E.CANCELADO])
def test_pedidos_cerrados_no_cambian(operador, centro, final):
    pedido = crear_pedido(centro, final)

    respuesta = api_de(operador).patch(
        url(pedido), {"estado": E.CANCELADO, "motivo": "x"}, format="json"
    )

    assert respuesta.status_code == 400
    assert respuesta.data["codigo"] == "pedido_cerrado"


def test_estado_inexistente_es_rechazado(cocina, centro):
    pedido = crear_pedido(centro)

    respuesta = api_de(cocina).patch(url(pedido), {"estado": "volando"}, format="json")

    assert respuesta.status_code == 400
    assert "estado" in respuesta.data


# --- Criterio 4: cada transición guarda fecha, hora y usuario ----------------------


def test_cada_transicion_queda_en_el_historial(cocina, centro):
    pedido = crear_pedido(centro)
    registrar_estado_inicial(pedido)
    api = api_de(cocina)

    api.patch(url(pedido), {"estado": E.EN_PREPARACION}, format="json")
    respuesta = api.patch(url(pedido), {"estado": E.LISTO_DESPACHO}, format="json")

    historial = respuesta.data["historial"]
    assert [h["estado"] for h in historial] == [E.RECIBIDO, E.EN_PREPARACION, E.LISTO_DESPACHO]
    assert all(h["fecha_hora"] for h in historial)
    assert historial[0]["usuario"] is None
    assert historial[1]["usuario"] == "cocina@correo.com"
    assert HistorialEstadoPedido.objects.filter(pedido=pedido).count() == 3


def test_consultar_estado_e_historial(cocina, centro):
    pedido = crear_pedido(centro)

    respuesta = api_de(cocina).get(url(pedido))

    assert respuesta.status_code == 200
    assert respuesta.data["estado"] == E.RECIBIDO
    assert respuesta.data["siguientes_estados"] == [E.EN_PREPARACION, E.CANCELADO]


# --- Roles y sedes ------------------------------------------------------------------


def test_cocina_no_aprueba_pedidos(cocina, centro):
    pedido = crear_pedido(centro, E.PENDIENTE_APROBACION)

    respuesta = api_de(cocina).patch(url(pedido), {"estado": E.RECIBIDO}, format="json")

    assert respuesta.status_code == 403
    assert respuesta.data["codigo"] == "rol_no_autorizado"


def test_operador_no_mueve_pedidos_en_cocina(operador, centro):
    pedido = crear_pedido(centro)

    respuesta = api_de(operador).patch(url(pedido), {"estado": E.EN_PREPARACION}, format="json")

    assert respuesta.status_code == 403


def test_operador_aprueba_pedido_pendiente(operador, centro):
    pedido = crear_pedido(centro, E.PENDIENTE_APROBACION)

    respuesta = api_de(operador).patch(url(pedido), {"estado": E.RECIBIDO}, format="json")

    assert respuesta.status_code == 200
    assert respuesta.data["historial"][-1]["usuario"] == "operador@correo.com"


def test_cocina_de_otra_sede_no_ve_el_pedido(centro, sur):
    cocina_sur, _ = crear_personal(COCINA, "cocinasur@correo.com", sur)
    pedido = crear_pedido(centro)

    assert api_de(cocina_sur).get(url(pedido)).status_code == 404
    assert api_de(cocina_sur).patch(url(pedido), {"estado": E.EN_PREPARACION}, format="json").status_code == 404


def test_administrador_ve_pedidos_de_cualquier_sede(sur):
    admin, _ = crear_personal(ADMINISTRADOR, "admin@correo.com")
    pedido = crear_pedido(sur)

    assert api_de(admin).get(url(pedido)).status_code == 200


def test_repartidor_avanza_solo_sus_pedidos(centro):
    usuario, empleado = crear_personal(REPARTIDOR, "repa@correo.com", centro)
    perfil = Repartidor.objects.create(empleado=empleado, disponible=True)
    suyo = crear_pedido(centro, E.LISTO_DESPACHO, "P-1", repartidor=perfil)
    ajeno = crear_pedido(centro, E.LISTO_DESPACHO, "P-2")
    api = api_de(usuario)

    for estado in (E.RECOGIDO, E.EN_CAMINO, E.ENTREGADO):
        assert api.patch(url(suyo), {"estado": estado}, format="json").status_code == 200
    assert api.patch(url(ajeno), {"estado": E.RECOGIDO}, format="json").status_code == 404


def test_cliente_cancela_su_pedido_antes_de_preparacion(centro):
    usuario, perfil = crear_cliente("ana@correo.com", "3001112233")
    pedido = crear_pedido(centro, cliente=perfil)

    respuesta = api_de(usuario).patch(url(pedido), {"estado": E.CANCELADO}, format="json")

    assert respuesta.status_code == 200
    assert respuesta.data["estado"] == E.CANCELADO


def test_cliente_no_cancela_si_ya_esta_en_preparacion(centro):
    usuario, perfil = crear_cliente("ana@correo.com", "3001112233")
    pedido = crear_pedido(centro, E.EN_PREPARACION, cliente=perfil)

    respuesta = api_de(usuario).patch(url(pedido), {"estado": E.CANCELADO}, format="json")

    assert respuesta.status_code == 403


def test_cliente_no_ve_pedidos_ajenos(centro):
    usuario, _ = crear_cliente("ana@correo.com", "3001112233")
    _, otro = crear_cliente("beto@correo.com", "3004445566")
    pedido = crear_pedido(centro, cliente=otro)

    assert api_de(usuario).get(url(pedido)).status_code == 404


def test_personal_debe_escribir_motivo_al_cancelar(operador, centro):
    pedido = crear_pedido(centro)
    api = api_de(operador)

    sin_motivo = api.patch(url(pedido), {"estado": E.CANCELADO}, format="json")
    assert sin_motivo.status_code == 400
    assert "motivo" in sin_motivo.data

    con_motivo = api.patch(url(pedido), {"estado": E.CANCELADO, "motivo": "Sin gas"}, format="json")
    assert con_motivo.status_code == 200
    pedido.refresh_from_db()
    assert pedido.motivo_cancelacion == "Sin gas"


def test_sin_sesion_responde_401(centro):
    assert api_de().get(url(crear_pedido(centro))).status_code == 401


def test_usuario_sin_rol_responde_403(centro):
    usuario = Usuario.objects.create_user(username="x@correo.com", email="x@correo.com", password=CLAVE)

    assert api_de(usuario).get(url(crear_pedido(centro))).status_code == 403


# --- Servicio (para reutilizar en HU-28, HU-45, HU-25, HU-34) ----------------------


def test_flujo_completo_por_roles():
    pasos = [
        (E.PENDIENTE_APROBACION, E.RECIBIDO, OPERADOR),
        (E.RECIBIDO, E.EN_PREPARACION, COCINA),
        (E.EN_PREPARACION, E.LISTO_DESPACHO, COCINA),
        (E.LISTO_DESPACHO, E.RECOGIDO, REPARTIDOR),
        (E.RECOGIDO, E.EN_CAMINO, REPARTIDOR),
        (E.EN_CAMINO, E.ENTREGADO, REPARTIDOR),
    ]
    for actual, nuevo, rol in pasos:
        validar_transicion(actual, nuevo, rol)  # no lanza error


def test_ninguna_transicion_sale_de_un_estado_final():
    assert not [t for t in TRANSICIONES if t[0] in (E.ENTREGADO, E.CANCELADO)]


def test_siguientes_estados_por_rol():
    assert siguientes_estados(E.RECIBIDO, COCINA) == [E.EN_PREPARACION, E.CANCELADO]
    assert siguientes_estados(E.LISTO_DESPACHO, REPARTIDOR) == [E.RECOGIDO]
    assert siguientes_estados(E.EN_CAMINO, COCINA) == []


def test_se_envia_senal_para_tiempo_real(cocina, centro, django_capture_on_commit_callbacks):
    pedido = crear_pedido(centro)
    recibidas = []

    def receptor(sender, pedido, estado_anterior, usuario, **kwargs):
        recibidas.append((pedido.estado, estado_anterior, usuario))

    estado_pedido_cambiado.connect(receptor)
    try:
        with django_capture_on_commit_callbacks(execute=True):
            cambiar_estado(pedido, E.EN_PREPARACION, usuario=cocina, rol=COCINA)
    finally:
        estado_pedido_cambiado.disconnect(receptor)

    assert recibidas == [(E.EN_PREPARACION, E.RECIBIDO, cocina)]


def test_error_de_transicion_trae_mensaje_legible():
    with pytest.raises(TransicionInvalida) as error:
        validar_transicion(E.RECIBIDO, E.LISTO_DESPACHO, COCINA)

    assert "no se pueden saltar pasos" in error.value.mensaje
