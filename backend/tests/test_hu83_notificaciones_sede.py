"""HU-83: el administrador suscribe roles o correos a los avisos de cada sede."""
from datetime import time

import pytest
from django.contrib.auth.models import Group
from django.core import mail
from rest_framework.test import APIClient

from inventario.models import InventarioProducto
from menu.models import CategoriaMenu, Producto
from pedidos.estados import ADMINISTRADOR, CLIENTE, COCINA, OPERADOR, cambiar_estado
from pedidos.models import EstadoPedido as E, Pedido
from sedes import notificaciones
from sedes.models import CapacidadSede, Ciudad, EventoSede, Sede, SuscripcionNotificacion
from sedes.notificaciones import destinatarios
from usuarios.models import Empleado, Usuario

pytestmark = pytest.mark.django_db

URL = "/api/notificaciones-sede/"
TODOS_LOS_DIAS = "lunes,martes,miercoles,jueves,viernes,sabado,domingo"


def _sede(nombre):
    ciudad, _ = Ciudad.objects.get_or_create(nombre="Cali")
    return Sede.objects.create(
        ciudad=ciudad, nombre=nombre, direccion="Calle 1 # 2-3", latitud=3.45,
        longitud=-76.53, barrio="Granada", telefono="3000000000", correo="s@correo.com",
    )


def _personal(rol, email, sede=None, activo=True):
    usuario = Usuario.objects.create_user(
        username=email, email=email, password="ClaveSegura2026", is_active=activo
    )
    usuario.groups.add(Group.objects.get_or_create(name=rol)[0])
    Empleado.objects.create(
        usuario=usuario, sede=sede, tipo_documento="CC", num_documento=email[:10],
        nombres="N", apellidos="A", celular="3001234567", direccion="Calle 4",
    )
    return usuario


def _suscribir(sede, evento, rol="", correo=""):
    return SuscripcionNotificacion.objects.create(sede=sede, evento=evento, rol=rol, correo=correo)


def _http(usuario):
    cliente = APIClient()
    cliente.force_authenticate(user=usuario)
    return cliente


def _destinos():
    """Cada correo enviado lleva un solo destinatario."""
    return sorted(correo.to[0] for correo in mail.outbox)


@pytest.fixture
def norte():
    return _sede("Norte")


@pytest.fixture
def admin():
    return _personal("administrador", "admin@correo.com")


# --- API del administrador -----------------------------------------------------------

def test_el_admin_suscribe_un_rol_y_un_correo(norte, admin):
    http = _http(admin)

    por_rol = http.post(URL, {"sede": norte.pk, "evento": "stock_bajo", "rol": "operador"}, format="json")
    por_correo = http.post(
        URL, {"sede": norte.pk, "evento": "stock_bajo", "correo": "  Gerente@Correo.com "}, format="json"
    )

    assert por_rol.status_code == 201, por_rol.data
    assert por_rol.data["rol_nombre"] == "Operadores de la sede"
    assert por_rol.data["evento_nombre"] == "Alerta de stock bajo"
    assert por_correo.status_code == 201, por_correo.data
    assert por_correo.data["correo"] == "gerente@correo.com"


def test_lista_solo_las_suscripciones_de_la_sede_pedida(norte, admin):
    sur = _sede("Sur")
    _suscribir(norte, EventoSede.CANCELACION, rol="operador")
    _suscribir(sur, EventoSede.CANCELACION, rol="cocina")

    respuesta = _http(admin).get(URL, {"sede": norte.pk})

    assert respuesta.status_code == 200
    assert [s["rol"] for s in respuesta.data] == ["operador"]


def test_sede_no_numerica_es_400(admin):
    assert _http(admin).get(URL, {"sede": "abc"}).status_code == 400


@pytest.mark.parametrize(
    "datos",
    [
        {"rol": "operador", "correo": "a@correo.com"},  # los dos
        {},  # ninguno
        {"rol": "cliente"},  # no es un rol del personal
        {"correo": "no-es-correo"},
    ],
)
def test_datos_invalidos_son_400(norte, admin, datos):
    respuesta = _http(admin).post(URL, {"sede": norte.pk, "evento": "sobrecupo", **datos}, format="json")
    assert respuesta.status_code == 400


def test_evento_desconocido_es_400(norte, admin):
    respuesta = _http(admin).post(URL, {"sede": norte.pk, "evento": "lluvia", "rol": "operador"}, format="json")
    assert respuesta.status_code == 400
    assert "evento" in respuesta.data


def test_no_permite_suscripciones_repetidas(norte, admin):
    _suscribir(norte, EventoSede.SOBRECUPO, rol="operador")
    _suscribir(norte, EventoSede.SOBRECUPO, correo="gerente@correo.com")
    http = _http(admin)

    rol = http.post(URL, {"sede": norte.pk, "evento": "sobrecupo", "rol": "operador"}, format="json")
    correo = http.post(URL, {"sede": norte.pk, "evento": "sobrecupo", "correo": "GERENTE@correo.com"}, format="json")
    # el mismo rol en OTRO evento sí se puede
    otro_evento = http.post(URL, {"sede": norte.pk, "evento": "stock_bajo", "rol": "operador"}, format="json")

    assert rol.status_code == 400 and "rol" in rol.data
    assert correo.status_code == 400 and "correo" in correo.data
    assert otro_evento.status_code == 201


def test_el_admin_quita_una_suscripcion(norte, admin):
    suscripcion = _suscribir(norte, EventoSede.STOCK_BAJO, rol="cocina")

    respuesta = _http(admin).delete(f"{URL}{suscripcion.pk}/")

    assert respuesta.status_code == 204
    assert not SuscripcionNotificacion.objects.exists()


@pytest.mark.parametrize("rol", ["operador", "cocina", "repartidor"])
def test_solo_el_administrador_configura(norte, rol):
    empleado = _personal(rol, f"{rol}@correo.com", norte)
    http = _http(empleado)

    assert http.get(URL).status_code == 403
    assert http.post(URL, {"sede": norte.pk, "evento": "stock_bajo", "rol": rol}, format="json").status_code == 403


def test_sin_sesion_es_401():
    assert APIClient().get(URL).status_code == 401


# --- A quién le llega ----------------------------------------------------------------

def test_un_rol_es_el_personal_activo_de_esa_sede(norte):
    sur = _sede("Sur")
    _personal("operador", "op.norte@correo.com", norte)
    _personal("operador", "op.inactivo@correo.com", norte, activo=False)
    _personal("operador", "op.sur@correo.com", sur)
    _personal("cocina", "cocina.norte@correo.com", norte)
    _suscribir(norte, EventoSede.CANCELACION, rol="operador")

    assert destinatarios(norte.pk, EventoSede.CANCELACION) == ["op.norte@correo.com"]
    # otro evento de la misma sede no tiene a nadie
    assert destinatarios(norte.pk, EventoSede.STOCK_BAJO) == []


def test_el_rol_administrador_son_todos_los_administradores(norte, admin):
    _personal("administrador", "admin2@correo.com")
    _suscribir(norte, EventoSede.SOBRECUPO, rol="administrador")

    assert destinatarios(norte.pk, EventoSede.SOBRECUPO) == ["admin2@correo.com", "admin@correo.com"]


def test_no_repite_un_correo_que_llega_por_rol_y_suelto(norte):
    _personal("operador", "op@correo.com", norte)
    _suscribir(norte, EventoSede.CANCELACION, rol="operador")
    _suscribir(norte, EventoSede.CANCELACION, correo="op@correo.com")
    _suscribir(norte, EventoSede.CANCELACION, correo="gerente@correo.com")

    assert destinatarios(norte.pk, EventoSede.CANCELACION) == ["gerente@correo.com", "op@correo.com"]


# --- Stock bajo (HU-16) ----------------------------------------------------------------

def _inventario(sede, stock=10, minimo=5):
    categoria, _ = CategoriaMenu.objects.get_or_create(nombre="Platos")
    producto = Producto.objects.create(
        categoria=categoria, nombre="Hamburguesa", precio_base=20000,
        tiempo_preparacion=15, tipo_control_stock=Producto.TipoControlStock.PRODUCTO,
    )
    return InventarioProducto.objects.create(sede=sede, producto=producto, stock_actual=stock, stock_minimo=minimo)


def _poner_stock(inventario, valor):
    inventario.stock_actual = valor
    inventario.save()


def test_stock_bajo_avisa_una_vez_a_los_suscritos(norte, django_capture_on_commit_callbacks):
    sur = _sede("Sur")
    _personal("operador", "op@correo.com", norte)
    _suscribir(norte, EventoSede.STOCK_BAJO, rol="operador")
    _suscribir(sur, EventoSede.STOCK_BAJO, correo="sur@correo.com")
    inventario = _inventario(norte)

    with django_capture_on_commit_callbacks(execute=True):
        _poner_stock(inventario, 4)
    assert _destinos() == ["op@correo.com"]
    correo = mail.outbox[0]
    assert correo.subject == "[Norte] Stock bajo: Hamburguesa"
    assert "quedó en 4 unidades" in correo.body and "mínimo de 5" in correo.body

    # sigue bajando: la alerta solo se actualiza, no llega otro correo
    with django_capture_on_commit_callbacks(execute=True):
        _poner_stock(inventario, 2)
    assert len(mail.outbox) == 1


def test_stock_bajo_sin_suscritos_no_envia_correo(norte, django_capture_on_commit_callbacks):
    inventario = _inventario(norte)

    with django_capture_on_commit_callbacks(execute=True):
        _poner_stock(inventario, 1)

    assert mail.outbox == []


# --- Cancelaciones -----------------------------------------------------------------------

def _pedido(sede, numero="P-1", estado=E.RECIBIDO):
    return Pedido.objects.create(numero_pedido=numero, sede=sede, estado=estado)


def test_cancelacion_de_la_sede_avisa_con_quien_y_motivo(norte, django_capture_on_commit_callbacks):
    operador = _personal("operador", "op@correo.com", norte)
    _suscribir(norte, EventoSede.CANCELACION, correo="gerente@correo.com")
    pedido = _pedido(norte)

    with django_capture_on_commit_callbacks(execute=True):
        cambiar_estado(pedido, E.CANCELADO, usuario=operador, rol=OPERADOR, motivo="Sin ingredientes")

    assert _destinos() == ["gerente@correo.com"]
    correo = mail.outbox[0]
    assert correo.subject == "[Norte] Pedido P-1 cancelado"
    assert "cancelado por el operador de la sede" in correo.body
    assert "Motivo: Sin ingredientes" in correo.body


def test_cancelacion_del_cliente_y_del_sistema(norte, django_capture_on_commit_callbacks):
    cliente = Usuario.objects.create_user(username="cli@correo.com", email="cli@correo.com", password="x")
    _suscribir(norte, EventoSede.CANCELACION, correo="gerente@correo.com")

    with django_capture_on_commit_callbacks(execute=True):
        cambiar_estado(_pedido(norte, "P-1"), E.CANCELADO, usuario=cliente, rol=CLIENTE, motivo="Ya no lo quiero")
        cambiar_estado(_pedido(norte, "P-2", E.PENDIENTE_APROBACION), E.CANCELADO, usuario=None,
                       rol=ADMINISTRADOR, motivo="Venció el tiempo de aprobación")

    cuerpos = [correo.body for correo in mail.outbox]
    assert "cancelado por el cliente" in cuerpos[0]
    assert "cancelado automáticamente por el sistema" in cuerpos[1]


def test_otros_cambios_de_estado_no_avisan(norte, django_capture_on_commit_callbacks):
    _suscribir(norte, EventoSede.CANCELACION, correo="gerente@correo.com")
    cocina = _personal("cocina", "cocina@correo.com", norte)

    with django_capture_on_commit_callbacks(execute=True):
        cambiar_estado(_pedido(norte), E.EN_PREPARACION, usuario=cocina, rol=COCINA)

    assert mail.outbox == []


def test_un_fallo_del_aviso_no_rompe_la_cancelacion(norte, monkeypatch, django_capture_on_commit_callbacks):
    _suscribir(norte, EventoSede.CANCELACION, correo="gerente@correo.com")
    operador = _personal("operador", "op@correo.com", norte)

    def falla(*args, **kwargs):
        raise RuntimeError("sin correo")

    monkeypatch.setattr(notificaciones, "destinatarios", falla)
    pedido = _pedido(norte)
    with django_capture_on_commit_callbacks(execute=True):
        cambiar_estado(pedido, E.CANCELADO, usuario=operador, rol=OPERADOR, motivo="Cliente no responde")

    pedido.refresh_from_db()
    assert pedido.estado == E.CANCELADO
    assert mail.outbox == []


# --- Sobrecupo (HU-60) ----------------------------------------------------------------

def test_sobrecupo_avisa_al_llegar_al_umbral_y_no_se_repite(norte, django_capture_on_commit_callbacks):
    CapacidadSede.objects.create(
        sede=norte, hora_inicio=time(0, 0), hora_fin=time(23, 59, 59), dias_semana=TODOS_LOS_DIAS,
        max_pedidos_simultaneos=5, umbral_alerta=4,
    )
    _personal("cocina", "cocina@correo.com", norte)
    _suscribir(norte, EventoSede.SOBRECUPO, rol="cocina")

    for numero in range(1, 4):
        with django_capture_on_commit_callbacks(execute=True):
            _pedido(norte, f"P-{numero}")
    assert mail.outbox == []

    with django_capture_on_commit_callbacks(execute=True):
        _pedido(norte, "P-4")
    assert _destinos() == ["cocina@correo.com"]
    assert mail.outbox[0].subject == "[Norte] Capacidad casi llena"
    assert "4 de 5 pedidos simultáneos" in mail.outbox[0].body

    # sigue sobre el umbral: no llega otro correo
    with django_capture_on_commit_callbacks(execute=True):
        _pedido(norte, "P-5")
    assert len(mail.outbox) == 1
