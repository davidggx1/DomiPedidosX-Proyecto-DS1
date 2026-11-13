"""Pruebas de SCRUM-119 · Celery y Redis: correos en segundo plano y vencimiento de pedidos."""
import os
import subprocess
import sys
from datetime import date, time, timedelta
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import pytest
from django.conf import settings
from django.core import mail
from django.core.management import call_command
from django.utils import timezone
from kombu.exceptions import OperationalError
from rest_framework.test import APIClient

from inventario.models import InventarioProducto
from menu.models import CategoriaMenu, Producto
from pedidos import vencimiento
from pedidos.capacidad import pedidos_que_ocupan_cupo
from pedidos.models import EstadoPedido as E
from pedidos.models import Notificacion, Pedido, TipoNotificacion
from pedidos.tasks import vencer_pedidos_pendientes
from sedes.models import Ciudad, Sede, ZonaCobertura
from usuarios.models import Cliente, DireccionEntrega, Usuario
from usuarios.tasks import encolar_correo, enviar_correo

BACKEND = Path(__file__).resolve().parents[1]


# =============================================================================
# Configuración
# =============================================================================


def test_sin_redis_las_tareas_corren_en_el_momento():
    from config.celery import app

    assert settings.CELERY_TASK_ALWAYS_EAGER is True
    assert app.conf.task_always_eager is True


def test_la_tarea_periodica_programada_existe():
    from config.celery import app

    nombre = settings.CELERY_BEAT_SCHEDULE["vencer-pedidos-pendientes"]["task"]
    app.loader.import_default_modules()

    assert nombre == vencer_pedidos_pendientes.name
    assert nombre in app.tasks


def _settings_con(**entorno):
    """Carga settings.py en otro proceso con variables de entorno distintas."""
    codigo = (
        "import config.settings as s; "
        "print(s.CHANNEL_LAYERS['default']['BACKEND']); print(s.CELERY_TASK_ALWAYS_EAGER)"
    )
    salida = subprocess.run(
        [sys.executable, "-c", codigo], cwd=BACKEND, env={**os.environ, **entorno},
        capture_output=True, text=True, check=True,
    )
    return salida.stdout.split()


def test_con_redis_el_tiempo_real_y_las_tareas_usan_redis():
    backend, eager = _settings_con(REDIS_URL="redis://localhost:6379/0")

    assert backend == "channels_redis.core.RedisChannelLayer"
    assert eager == "False"


def test_sin_redis_el_tiempo_real_usa_memoria():
    backend, eager = _settings_con(REDIS_URL="", CELERY_BROKER_URL="")

    assert backend == "channels.layers.InMemoryChannelLayer"
    assert eager == "True"


# =============================================================================
# Correos
# =============================================================================


def test_encolar_correo_lo_envia():
    encolar_correo("Asunto", "Cuerpo", ["ana@correo.com"])

    assert len(mail.outbox) == 1
    assert mail.outbox[0].to == ["ana@correo.com"]
    assert mail.outbox[0].from_email == settings.DEFAULT_FROM_EMAIL


def test_si_falla_el_servidor_de_correo_no_rompe_nada(monkeypatch):
    def falla(*args, **kwargs):
        raise ConnectionError("sin servidor de correo")

    monkeypatch.setattr("usuarios.tasks.send_mail", falla)

    encolar_correo("Asunto", "Cuerpo", ["ana@correo.com"])  # no lanza

    assert mail.outbox == []


def test_si_redis_no_responde_se_envia_en_el_momento(monkeypatch):
    def sin_redis(*args, **kwargs):
        raise OperationalError("Redis no responde")

    monkeypatch.setattr(enviar_correo, "delay", sin_redis)

    encolar_correo("Asunto", "Cuerpo", ["ana@correo.com"])

    assert len(mail.outbox) == 1


class Reintento(Exception):
    pass


def test_con_worker_un_fallo_se_reintenta(monkeypatch):
    monkeypatch.setattr("usuarios.tasks.send_mail", lambda **kw: (_ for _ in ()).throw(ConnectionError()))
    monkeypatch.setattr(enviar_correo, "retry", lambda exc: Reintento())

    enviar_correo.push_request(is_eager=False, retries=0)
    try:
        with pytest.raises(Reintento):
            enviar_correo.run("Asunto", "Cuerpo", ["ana@correo.com"])
    finally:
        enviar_correo.pop_request()


def test_con_worker_tras_el_ultimo_reintento_se_rinde_sin_error(monkeypatch):
    monkeypatch.setattr("usuarios.tasks.send_mail", lambda **kw: (_ for _ in ()).throw(ConnectionError()))

    enviar_correo.push_request(is_eager=False, retries=enviar_correo.max_retries)
    try:
        assert enviar_correo.run("Asunto", "Cuerpo", ["ana@correo.com"]) is None
    finally:
        enviar_correo.pop_request()


@pytest.mark.django_db
def test_el_correo_de_restablecer_contrasena_va_por_la_cola():
    Usuario.objects.create_user(username="ana@correo.com", email="ana@correo.com", password="ClaveSegura2026")

    respuesta = APIClient().post("/api/usuarios/contrasena/solicitar/", {"email": "ana@correo.com"}, format="json")

    assert respuesta.status_code == 200
    assert len(mail.outbox) == 1
    assert "restablecer-contrasena?uid=" in mail.outbox[0].body


@pytest.mark.django_db
def test_si_falla_el_correo_de_restablecer_la_respuesta_no_cambia(monkeypatch):
    Usuario.objects.create_user(username="ana@correo.com", email="ana@correo.com", password="ClaveSegura2026")
    monkeypatch.setattr("usuarios.tasks.send_mail", lambda **kw: (_ for _ in ()).throw(ConnectionError()))

    con_cuenta = APIClient().post("/api/usuarios/contrasena/solicitar/", {"email": "ana@correo.com"}, format="json")
    sin_cuenta = APIClient().post("/api/usuarios/contrasena/solicitar/", {"email": "nadie@correo.com"}, format="json")

    assert con_cuenta.status_code == sin_cuenta.status_code == 200
    assert con_cuenta.data == sin_cuenta.data


# =============================================================================
# Vencimiento de pedidos pendientes
# =============================================================================


@pytest.fixture
def m(db):
    ciudad = Ciudad.objects.create(nombre="Cali")
    sede = Sede.objects.create(
        ciudad=ciudad, nombre="Norte", direccion="Calle 1 # 2-3", latitud=3.45,
        longitud=-76.53, barrio="Granada", telefono="3000000000", correo="s@correo.com",
    )
    ZonaCobertura.objects.create(
        sede=sede, nombre="Zona 1", radio=5, centro_latitud=3.45, centro_longitud=-76.53,
        tarifa_domicilio=Decimal("3000"), tiempo_estimado=40, pedido_minimo=Decimal("0"),
    )
    usuario = Usuario.objects.create_user(username="cli@correo.com", email="cli@correo.com", password="ClaveSegura2026")
    cliente = Cliente.objects.create(
        usuario=usuario, tipo_documento="CC", num_documento="3001234567", nombres="Ana",
        apellidos="Prueba", celular="3001234567", fecha_nacimiento=date(2000, 1, 1),
    )
    direccion = DireccionEntrega.objects.create(
        ciudad=ciudad, cliente=cliente, direccion="Calle 5 # 6-7", latitud=3.46, longitud=-76.53,
    )
    categoria = CategoriaMenu.objects.create(nombre="Platos")
    producto = Producto.objects.create(
        categoria=categoria, nombre="Hamburguesa", precio_base=Decimal("20000"),
        tiempo_preparacion=15, tipo_control_stock=Producto.TipoControlStock.PRODUCTO,
    )
    inv = InventarioProducto.objects.create(sede=sede, producto=producto, stock_actual=5)
    from sedes.models import CapacidadSede

    CapacidadSede.objects.create(
        sede=sede, hora_inicio=time(0, 0), hora_fin=time(23, 59, 59),
        dias_semana="lunes,martes,miercoles,jueves,viernes,sabado,domingo",
        max_pedidos_simultaneos=10, umbral_alerta=8,
    )
    return SimpleNamespace(sede=sede, usuario=usuario, direccion=direccion, producto=producto, inv=inv)


def confirmar(m, minutos_atras=0):
    api = APIClient()
    api.force_authenticate(m.usuario)
    respuesta = api.post(
        "/api/pedidos/confirmar/",
        {
            "sede_id": m.sede.pk, "direccion_id": m.direccion.pk, "metodo_pago": "efectivo",
            "items": [{"producto_id": m.producto.pk, "cantidad": 2}],
        },
        format="json",
    )
    assert respuesta.status_code == 201, respuesta.data
    pedido = Pedido.objects.latest("pk")
    Pedido.objects.filter(pk=pedido.pk).update(fecha_creacion=timezone.now() - timedelta(minutes=minutos_atras))
    mail.outbox.clear()
    return pedido


def test_un_pedido_vencido_se_cancela_y_devuelve_el_stock(m, django_capture_on_commit_callbacks):
    pedido = confirmar(m, minutos_atras=25)
    m.inv.refresh_from_db()
    assert m.inv.stock_actual == 3  # retenido al confirmar

    with django_capture_on_commit_callbacks(execute=True):
        assert vencimiento.vencer_pendientes() == 1

    pedido.refresh_from_db()
    m.inv.refresh_from_db()
    assert pedido.estado == E.CANCELADO
    assert "no lo aprobó en 20 minutos" in pedido.motivo_cancelacion
    assert pedido.historial_estados.latest("pk").usuario is None  # lo hizo el sistema
    assert m.inv.stock_actual == 5


def test_al_vencer_libera_el_cupo_de_la_sede(m):
    confirmar(m, minutos_atras=25)
    assert pedidos_que_ocupan_cupo(m.sede) == 1

    vencimiento.vencer_pendientes()

    assert pedidos_que_ocupan_cupo(m.sede) == 0


def test_al_vencer_avisa_al_cliente(m, django_capture_on_commit_callbacks):
    pedido = confirmar(m, minutos_atras=25)

    with django_capture_on_commit_callbacks(execute=True):
        vencimiento.vencer_pendientes()

    assert Notificacion.objects.filter(pedido=pedido, tipo=TipoNotificacion.PEDIDO_CANCELADO).exists()
    assert len(mail.outbox) == 1
    assert mail.outbox[0].to == ["cli@correo.com"]
    assert pedido.numero_pedido in mail.outbox[0].subject


def test_no_toca_pedidos_recientes_ni_aprobados(m):
    reciente = confirmar(m, minutos_atras=5)
    aprobado = confirmar(m, minutos_atras=60)
    Pedido.objects.filter(pk=aprobado.pk).update(estado=E.RECIBIDO)

    assert vencimiento.vencer_pendientes() == 0

    reciente.refresh_from_db()
    aprobado.refresh_from_db()
    assert reciente.estado == E.PENDIENTE_APROBACION
    assert aprobado.estado == E.RECIBIDO


def test_si_lo_aprueban_justo_antes_de_vencer_no_se_cancela(m, monkeypatch):
    pedido = confirmar(m, minutos_atras=60)
    # Simula que el operador lo aprobó entre la consulta y el bloqueo de la fila
    monkeypatch.setattr(vencimiento, "pedidos_vencidos", lambda ahora=None: Pedido.objects.filter(pk=pedido.pk))
    Pedido.objects.filter(pk=pedido.pk).update(estado=E.RECIBIDO)

    assert vencimiento.vencer_pendientes() == 0

    pedido.refresh_from_db()
    assert pedido.estado == E.RECIBIDO


def test_volver_a_ejecutar_no_hace_nada(m):
    confirmar(m, minutos_atras=25)

    assert vencimiento.vencer_pendientes() == 1
    assert vencimiento.vencer_pendientes() == 0


def test_con_cero_minutos_el_vencimiento_esta_desactivado(m, settings):
    settings.PEDIDO_PENDIENTE_MINUTOS = 0
    confirmar(m, minutos_atras=600)

    assert vencimiento.vencer_pendientes() == 0


def test_la_tarea_periodica_y_el_comando_vencen_pedidos(m, capsys):
    confirmar(m, minutos_atras=25)
    assert vencer_pedidos_pendientes() == 1

    confirmar(m, minutos_atras=25)
    call_command("vencer_pedidos_pendientes")

    assert "1 pedido(s) cancelado(s)" in capsys.readouterr().out
