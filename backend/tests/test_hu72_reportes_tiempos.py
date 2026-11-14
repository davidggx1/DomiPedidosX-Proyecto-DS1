"""Pruebas de HU-72 · Reportes de tiempos y desempeño (SCRUM-140)."""
from datetime import date, datetime, timedelta

import pytest
from django.contrib.auth.models import Group
from django.utils import timezone
from rest_framework.test import APIClient

from pedidos.models import EstadoPedido as E
from pedidos.models import HistorialEstadoPedido, Pedido
from pedidos.rango_fechas import RangoFechasInvalido, leer_rango_fechas
from sedes.models import Ciudad, Sede
from usuarios.models import Empleado, Repartidor, Usuario
from usuarios.roles import ADMINISTRADOR, OPERADOR

pytestmark = pytest.mark.django_db

URL = "/api/pedidos/reportes/tiempos/"
SEMANA = {"desde": "2026-11-09", "hasta": "2026-11-15"}

# Recorrido completo de un pedido web: minutos desde la creación hasta cada estado
WEB = {
    E.PENDIENTE_APROBACION: 0,
    E.RECIBIDO: 2,
    E.EN_PREPARACION: 5,
    E.LISTO_DESPACHO: 20,
    E.RECOGIDO: 25,
    E.EN_CAMINO: 26,
    E.ENTREGADO: 40,
}


def _hora_local(dia, hora=12):
    return timezone.make_aware(datetime.combine(dia, datetime.min.time()).replace(hour=hora))


def _sede(nombre):
    ciudad, _ = Ciudad.objects.get_or_create(nombre="Cali")
    return Sede.objects.create(
        ciudad=ciudad, nombre=nombre, direccion="Calle 1 # 2-3", latitud=3.45, longitud=-76.53,
        barrio="Centro", telefono="3000000000", correo=f"{nombre.lower()}@correo.com",
    )


def _repartidor(nombres, apellidos, sede):
    usuario = Usuario.objects.create_user(username=f"{nombres}@correo.com", email=f"{nombres}@correo.com", password="x")
    empleado = Empleado.objects.create(
        usuario=usuario, sede=sede, tipo_documento="CC", num_documento=nombres[:10], nombres=nombres,
        apellidos=apellidos, celular="3001234567", direccion="Calle 4",
    )
    return Repartidor.objects.create(empleado=empleado)


def _pedido(sede, numero, pasos=WEB, dia=date(2026, 11, 10), repartidor=None, estado=None):
    """Pedido creado `dia` a las 12:00 locales, con una marca de historial por cada paso."""
    creado = _hora_local(dia)
    estado_final = estado or max(pasos, key=pasos.get)
    pedido = Pedido.objects.create(sede=sede, numero_pedido=numero, estado=estado_final, repartidor=repartidor)
    Pedido.objects.filter(pk=pedido.pk).update(fecha_creacion=creado)
    for estado_paso, minuto in pasos.items():
        paso = HistorialEstadoPedido.objects.create(pedido=pedido, estado=estado_paso)
        HistorialEstadoPedido.objects.filter(pk=paso.pk).update(fecha_hora=creado + timedelta(minutes=minuto))
    return pedido


def _con_rol(rol):
    usuario = Usuario.objects.create_user(username=f"{rol}@correo.com", email=f"{rol}@correo.com", password="x")
    usuario.groups.add(Group.objects.get_or_create(name=rol)[0])
    api = APIClient()
    api.force_authenticate(usuario)
    return api


@pytest.fixture
def centro():
    return _sede("Centro")


@pytest.fixture
def admin():
    return _con_rol(ADMINISTRADOR)


def _fase(datos, clave):
    return next(f for f in datos["fases"] if f["fase"] == clave)


# --- Criterio 1: tiempo promedio por fase -----------------------------------------


def test_desglosa_el_promedio_de_cada_fase(admin, centro):
    _pedido(centro, "P-1")
    # Segundo pedido: cada fase dura el doble
    _pedido(centro, "P-2", pasos={estado: minuto * 2 for estado, minuto in WEB.items()})

    datos = admin.get(URL, SEMANA).json()

    assert [f["fase"] for f in datos["fases"]] == ["aprobacion", "preparacion", "despacho", "entrega"]
    assert _fase(datos, "aprobacion")["promedio_minutos"] == 3.0  # (2 + 4) / 2
    assert _fase(datos, "preparacion")["promedio_minutos"] == 27.0  # (18 + 36) / 2
    assert _fase(datos, "despacho")["promedio_minutos"] == 9.0  # (6 + 12) / 2
    assert _fase(datos, "entrega")["promedio_minutos"] == 21.0  # (14 + 28) / 2
    assert datos["ciclo_promedio_minutos"] == 60.0  # (40 + 80) / 2
    assert all(f["pedidos"] == 2 for f in datos["fases"])


def test_los_pedidos_del_operador_no_cuentan_en_aprobacion(admin, centro):
    _pedido(centro, "P-1")
    # Pedido telefónico: nace "recibido", nunca estuvo pendiente de aprobación
    sin_aprobacion = {estado: minuto for estado, minuto in WEB.items() if estado != E.PENDIENTE_APROBACION}
    _pedido(centro, "P-2", pasos=sin_aprobacion)

    datos = admin.get(URL, SEMANA).json()

    aprobacion = _fase(datos, "aprobacion")
    assert (aprobacion["pedidos"], aprobacion["promedio_minutos"]) == (1, 2.0)
    assert _fase(datos, "preparacion")["pedidos"] == 2


def test_redondea_a_un_decimal(admin, centro):
    _pedido(centro, "P-1", pasos={**WEB, E.RECIBIDO: 1})
    _pedido(centro, "P-2", pasos={**WEB, E.RECIBIDO: 1})
    _pedido(centro, "P-3", pasos={**WEB, E.RECIBIDO: 2})

    assert _fase(admin.get(URL, SEMANA).json(), "aprobacion")["promedio_minutos"] == 1.3


# --- Criterio 2: desempeño por repartidor -------------------------------------------


def test_detalla_entregas_y_ciclo_promedio_por_repartidor(admin, centro):
    ana = _repartidor("Ana", "Gómez", centro)
    luis = _repartidor("Luis", "Pérez", centro)
    _pedido(centro, "P-1", repartidor=ana)
    _pedido(centro, "P-2", repartidor=ana, pasos={**WEB, E.ENTREGADO: 50})
    _pedido(centro, "P-3", repartidor=luis)

    filas = admin.get(URL, SEMANA).json()["repartidores"]

    assert filas == [
        {"id": ana.pk, "nombre": "Ana Gómez", "pedidos_entregados": 2,
         "ciclo_promedio_minutos": 45.0, "reparto_promedio_minutos": 25.0},  # (20 + 30) / 2
        {"id": luis.pk, "nombre": "Luis Pérez", "pedidos_entregados": 1,
         "ciclo_promedio_minutos": 40.0, "reparto_promedio_minutos": 20.0},
    ]


# --- Criterio 3: solo pedidos entregados ----------------------------------------------


def test_solo_cuenta_pedidos_entregados(admin, centro):
    ana = _repartidor("Ana", "Gómez", centro)
    _pedido(centro, "P-1", repartidor=ana)
    en_camino = {estado: minuto for estado, minuto in WEB.items() if estado != E.ENTREGADO}
    _pedido(centro, "P-2", pasos=en_camino, repartidor=ana)
    _pedido(centro, "P-3", pasos={**en_camino, E.CANCELADO: 60}, repartidor=ana)

    datos = admin.get(URL, SEMANA).json()

    assert datos["pedidos_entregados"] == 1
    assert _fase(datos, "despacho")["pedidos"] == 1
    assert datos["repartidores"][0]["pedidos_entregados"] == 1


# --- Criterio 4: sin datos ---------------------------------------------------------------


def test_rango_sin_entregas_avisa(admin, centro):
    _pedido(centro, "P-1", dia=date(2026, 10, 1))

    respuesta = admin.get(URL, SEMANA)

    assert respuesta.status_code == 200
    datos = respuesta.json()
    assert datos["sin_datos"] is True
    assert datos["mensaje"] == "No hay pedidos entregados en el rango seleccionado."
    assert datos["pedidos_entregados"] == 0
    assert datos["ciclo_promedio_minutos"] is None
    assert all(f["promedio_minutos"] is None and f["pedidos"] == 0 for f in datos["fases"])
    assert datos["repartidores"] == []


# --- Filtros -------------------------------------------------------------------------------


def test_el_rango_incluye_los_dos_extremos(admin, centro):
    _pedido(centro, "P-lunes", dia=date(2026, 11, 9))
    _pedido(centro, "P-domingo", dia=date(2026, 11, 15))
    _pedido(centro, "P-fuera", dia=date(2026, 11, 16))

    datos = admin.get(URL, SEMANA).json()

    assert datos["pedidos_entregados"] == 2
    assert (datos["desde"], datos["hasta"]) == ("2026-11-09", "2026-11-15")


def test_filtra_por_sede(admin, centro):
    sur = _sede("Sur")
    _pedido(centro, "P-1")
    _pedido(sur, "P-2", pasos={**WEB, E.ENTREGADO: 100})

    datos = admin.get(URL, {**SEMANA, "sede": sur.pk}).json()

    assert datos["sede"] == {"id": sur.pk, "nombre": "Sur"}
    assert datos["pedidos_entregados"] == 1
    assert datos["ciclo_promedio_minutos"] == 100.0
    assert admin.get(URL, SEMANA).json()["pedidos_entregados"] == 2


def test_sin_fechas_son_los_ultimos_siete_dias(admin, centro, monkeypatch):
    monkeypatch.setattr(timezone, "now", lambda: _hora_local(date(2026, 11, 15), hora=20))
    _pedido(centro, "P-dentro", dia=date(2026, 11, 9))
    _pedido(centro, "P-fuera", dia=date(2026, 11, 8))

    datos = admin.get(URL).json()

    assert (datos["desde"], datos["hasta"]) == ("2026-11-09", "2026-11-15")
    assert datos["pedidos_entregados"] == 1


@pytest.mark.parametrize(
    ("parametros", "campo"),
    [
        ({"desde": "2026-11-15", "hasta": "2026-11-09"}, "desde"),  # inicio posterior al fin
        ({"desde": "15/11/2026"}, "desde"),
        ({"hasta": "mañana"}, "hasta"),
        ({"desde": "2025-01-01", "hasta": "2026-11-15"}, "desde"),  # más de un año
        ({"sede": "abc"}, "sede"),
    ],
)
def test_parametros_invalidos_son_400(admin, parametros, campo):
    respuesta = admin.get(URL, parametros)

    assert respuesta.status_code == 400
    assert campo in respuesta.json()


def test_inicio_posterior_al_fin_explica_el_error(admin):
    respuesta = admin.get(URL, {"desde": "2026-11-15", "hasta": "2026-11-09"})
    assert respuesta.json()["desde"] == "La fecha de inicio no puede ser posterior a la fecha de fin."


def test_sede_inexistente_es_404(admin):
    assert admin.get(URL, {"sede": 9999}).status_code == 404


# --- Permisos -------------------------------------------------------------------------------


def test_solo_el_administrador(centro):
    assert APIClient().get(URL).status_code == 401
    assert _con_rol(OPERADOR).get(URL).status_code == 403


# --- Rango de fechas (reutilizable en la HU-71) ------------------------------------------------


def test_leer_rango_fechas_devuelve_limites_en_hora_local():
    desde, hasta, inicio, fin = leer_rango_fechas({"desde": "2026-11-09", "hasta": "2026-11-09"})

    assert desde == hasta == date(2026, 11, 9)
    assert inicio == _hora_local(date(2026, 11, 9), hora=0)
    assert fin - inicio == timedelta(days=1)


def test_leer_rango_fechas_solo_desde_llega_hasta_hoy():
    desde, hasta, *_ = leer_rango_fechas({"desde": "2026-11-01"}, hoy=date(2026, 11, 13))
    assert (desde, hasta) == (date(2026, 11, 1), date(2026, 11, 13))

    with pytest.raises(RangoFechasInvalido):
        leer_rango_fechas({"desde": "2026-11-20"}, hoy=date(2026, 11, 13))
