"""Pruebas de HU-64 · Cupo diario de usos de promociones y combos."""
import threading
from datetime import timedelta

import pytest
from django.db import IntegrityError, connection, transaction
from django.contrib.auth.models import Group
from django.utils import timezone
from rest_framework.test import APIClient

from pedidos.models import ConsumoCupoCombo, EstadoPedido, Pedido
from promociones import cupos
from promociones.cupos import CupoAgotado
from promociones.models import Combo, ComboSede, ConsumoCupoPromocion, Promocion
from sedes.models import Ciudad, Sede
from usuarios.models import Empleado, Usuario
from usuarios.roles import ADMINISTRADOR, OPERADOR

pytestmark = pytest.mark.django_db

URL = "/api/promociones/"


def _sede(nombre="Centro"):
    ciudad, _ = Ciudad.objects.get_or_create(nombre="Cali")
    return Sede.objects.create(
        ciudad=ciudad, nombre=nombre, direccion="Calle 1 # 2-3", latitud=3.45,
        longitud=-76.53, barrio="Granada", telefono="3000000000", correo="s@correo.com",
    )


def _promocion(sede, cupo=None, nombre="Promo"):
    hoy = timezone.localdate()
    return Promocion.objects.create(
        sede=sede, nombre=nombre, tipo_descuento="porcentaje", valor=10,
        fecha_inicio=hoy, fecha_fin=hoy + timedelta(days=5), cupo_max_diario=cupo,
    )


def _combo_sede(sede, cupo=None):
    hoy = timezone.localdate()
    combo = Combo.objects.create(
        nombre="Combo", precio=20000, fecha_inicio=hoy, fecha_vencimiento=hoy + timedelta(days=5)
    )
    return ComboSede.objects.create(combo=combo, sede=sede, cupo_max_diario=cupo)


_folio = iter(range(1, 10_000))


def _pedido(sede, estado=EstadoPedido.RECIBIDO):
    return Pedido.objects.create(numero_pedido=f"P-T-{next(_folio):04d}", sede=sede, estado=estado)


def _en_otra_fecha(consumo, dias):
    """Mueve un consumo a otro día (fecha_consumo es auto_now_add en combos)."""
    type(consumo).objects.filter(pk=consumo.pk).update(
        fecha_consumo=timezone.now() + timedelta(days=dias)
    )


@pytest.fixture
def sede():
    return _sede()


# --- Criterio 1: límite entero > 0, opcional ---------------------------------------


def test_sin_cupo_no_hay_limite(sede):
    promo = _promocion(sede)
    assert cupos.cupo_restante(promo) is None
    for _ in range(3):
        cupos.consumir(promo, _pedido(sede))
    assert cupos.usos_hoy(promo) == 3


def test_la_base_rechaza_cupo_cero(sede):
    with pytest.raises(IntegrityError), transaction.atomic():
        _promocion(sede, cupo=0)


# --- Criterios 2 y 3: cada pedido resta 1; al agotarse, bloquea ---------------------


def test_cada_pedido_resta_una_unidad(sede):
    promo = _promocion(sede, cupo=3)
    assert cupos.cupo_restante(promo) == 3
    cupos.consumir(promo, _pedido(sede))
    assert cupos.usos_hoy(promo) == 1
    assert cupos.cupo_restante(promo) == 2


def test_al_agotarse_bloquea_e_informa(sede):
    promo = _promocion(sede, cupo=2)
    cupos.consumir(promo, _pedido(sede))
    cupos.consumir(promo, _pedido(sede))
    with pytest.raises(CupoAgotado) as error:
        cupos.consumir(promo, _pedido(sede))
    assert "Promo" in error.value.mensaje and "agotó" in error.value.mensaje
    assert error.value.restante == 0
    assert ConsumoCupoPromocion.objects.count() == 2


def test_un_pedido_no_puede_usar_dos_promociones(sede):
    pedido = _pedido(sede)
    cupos.consumir(_promocion(sede, nombre="A"), pedido)
    with pytest.raises(IntegrityError), transaction.atomic():
        cupos.consumir(_promocion(sede, nombre="B"), pedido)


def test_el_cupo_de_una_promocion_no_afecta_a_otra(sede):
    a, b = _promocion(sede, 1, "A"), _promocion(sede, 1, "B")
    cupos.consumir(a, _pedido(sede))
    assert cupos.cupo_restante(b) == 1


# --- Criterio 4: reinicio a las 00:00 -----------------------------------------------


def test_los_usos_de_ayer_no_cuentan_hoy(sede):
    promo = _promocion(sede, cupo=1)
    consumo = cupos.consumir(promo, _pedido(sede))
    _en_otra_fecha(consumo, -1)
    assert cupos.usos_hoy(promo) == 0
    assert cupos.cupo_restante(promo) == 1
    cupos.consumir(promo, _pedido(sede))  # hoy vuelve a haber cupo


def test_el_dia_cambia_a_medianoche_de_bogota(sede):
    promo = _promocion(sede, cupo=1)
    consumo = cupos.consumir(promo, _pedido(sede))
    ahora = timezone.localtime()
    # Un uso a las 23:59 de ayer (hora local) cuenta para ayer, no para hoy.
    ayer_2359 = ahora.replace(hour=23, minute=59, second=0, microsecond=0) - timedelta(days=1)
    ConsumoCupoPromocion.objects.filter(pk=consumo.pk).update(fecha_consumo=ayer_2359)
    assert cupos.usos_hoy(promo) == 0
    # Uno a las 00:01 de hoy (hora local) sí cuenta.
    hoy_0001 = ahora.replace(hour=0, minute=1, second=0, microsecond=0)
    ConsumoCupoPromocion.objects.filter(pk=consumo.pk).update(fecha_consumo=hoy_0001)
    assert cupos.usos_hoy(promo) == 1


# --- Criterio 5: cancelar el mismo día restituye la unidad ---------------------------


def test_cancelar_el_mismo_dia_devuelve_la_unidad(sede):
    promo = _promocion(sede, cupo=1)
    pedido = _pedido(sede)
    cupos.consumir(promo, pedido)
    assert cupos.cupo_restante(promo) == 0
    Pedido.objects.filter(pk=pedido.pk).update(estado=EstadoPedido.CANCELADO)
    assert cupos.cupo_restante(promo) == 1
    cupos.consumir(promo, _pedido(sede))


def test_cancelar_un_pedido_de_ayer_no_toca_el_cupo_de_hoy(sede):
    promo = _promocion(sede, cupo=2)
    ayer = cupos.consumir(promo, _pedido(sede))
    _en_otra_fecha(ayer, -1)
    cupos.consumir(promo, _pedido(sede))
    Pedido.objects.filter(pk=ayer.pedido_id).update(estado=EstadoPedido.CANCELADO)
    assert cupos.usos_hoy(promo) == 1
    assert cupos.cupo_restante(promo) == 1


# --- Combos: misma regla, mismo módulo ----------------------------------------------


def test_combo_cuenta_unidades_y_respeta_cancelaciones(sede):
    cs = _combo_sede(sede, cupo=5)
    p1, p2 = _pedido(sede), _pedido(sede)
    cupos.consumir(cs, p1, cantidad=3)
    cupos.consumir(cs, p2, cantidad=2)
    assert cupos.cupo_restante(cs) == 0
    with pytest.raises(CupoAgotado):
        cupos.consumir(cs, _pedido(sede))
    Pedido.objects.filter(pk=p1.pk).update(estado=EstadoPedido.CANCELADO)
    assert cupos.cupo_restante(cs) == 3
    assert ConsumoCupoCombo.objects.count() == 2


def test_combo_no_deja_pasarse_con_una_cantidad_grande(sede):
    cs = _combo_sede(sede, cupo=2)
    with pytest.raises(CupoAgotado) as error:
        cupos.consumir(cs, _pedido(sede), cantidad=3)
    assert error.value.restante == 2


# --- API del administrador/operador --------------------------------------------------


def _personal(rol, email, sede):
    usuario = Usuario.objects.create_user(username=email, email=email, password="ClaveSegura2026")
    usuario.groups.add(Group.objects.get_or_create(name=rol)[0])
    Empleado.objects.create(
        usuario=usuario, sede=sede, tipo_documento="CC", num_documento=email[:10],
        nombres="N", apellidos="A", celular="3001234567", direccion="Calle 4",
    )
    return usuario


def _api(usuario):
    cliente = APIClient()
    cliente.force_authenticate(usuario)
    return cliente


def _datos(**cambios):
    hoy = timezone.localdate()
    base = {
        "nombre": "Con cupo", "tipo_descuento": "porcentaje", "valor": "10.00",
        "fecha_inicio": str(hoy), "fecha_fin": str(hoy + timedelta(days=3)),
    }
    base.update(cambios)
    return base


def test_el_operador_fija_el_cupo_y_ve_lo_que_queda(sede):
    api = _api(_personal(OPERADOR, "operador@correo.com", sede))
    respuesta = api.post(URL, _datos(cupo_max_diario=2), format="json")
    assert respuesta.status_code == 201
    assert respuesta.data["cupo_max_diario"] == 2
    assert respuesta.data["usos_hoy"] == 0
    assert respuesta.data["cupo_restante"] == 2

    promo = Promocion.objects.get(pk=respuesta.data["id"])
    cupos.consumir(promo, _pedido(sede))
    detalle = api.get(f"{URL}{promo.pk}/")
    assert detalle.data["usos_hoy"] == 1
    assert detalle.data["cupo_restante"] == 1


def test_sin_cupo_la_api_devuelve_null(sede):
    api = _api(_personal(OPERADOR, "operador@correo.com", sede))
    respuesta = api.post(URL, _datos(), format="json")
    assert respuesta.status_code == 201
    assert respuesta.data["cupo_max_diario"] is None
    assert respuesta.data["cupo_restante"] is None


@pytest.mark.parametrize("malo", [0, -5, "abc", 2.5])
def test_la_api_rechaza_cupos_invalidos(sede, malo):
    api = _api(_personal(OPERADOR, "operador@correo.com", sede))
    respuesta = api.post(URL, _datos(cupo_max_diario=malo), format="json")
    assert respuesta.status_code == 400
    assert "cupo_max_diario" in respuesta.data


def test_se_puede_quitar_el_cupo_editando(sede):
    api = _api(_personal(OPERADOR, "operador@correo.com", sede))
    promo = _promocion(sede, cupo=5)
    respuesta = api.patch(f"{URL}{promo.pk}/", {"cupo_max_diario": None}, format="json")
    assert respuesta.status_code == 200
    assert respuesta.data["cupo_max_diario"] is None


# --- Concurrencia ---------------------------------------------------------------------


@pytest.mark.django_db(transaction=True)
@pytest.mark.skipif(
    connection.vendor != "postgresql",
    reason="select_for_update solo bloquea de verdad en PostgreSQL (SQLite lo ignora).",
)
def test_dos_pedidos_simultaneos_no_se_pasan_del_cupo():
    sede = _sede("Concurrencia")
    promo = _promocion(sede, cupo=1)
    pedidos = [_pedido(sede) for _ in range(5)]
    resultados, barrera = [], threading.Barrier(len(pedidos))

    def intentar(pedido):
        try:
            barrera.wait()
            with transaction.atomic():
                cupos.consumir(promo, pedido)
            resultados.append("ok")
        except CupoAgotado:
            resultados.append("agotado")
        finally:
            connection.close()

    hilos = [threading.Thread(target=intentar, args=(p,)) for p in pedidos]
    [h.start() for h in hilos]
    [h.join() for h in hilos]

    assert resultados.count("ok") == 1
    assert resultados.count("agotado") == 4
    assert ConsumoCupoPromocion.objects.filter(promocion=promo).count() == 1