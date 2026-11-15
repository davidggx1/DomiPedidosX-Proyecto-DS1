"""Pruebas de HU-84 · Gestionar promociones (crear, editar y desactivar)."""
from datetime import timedelta

import pytest
from django.contrib.auth.models import Group
from django.utils import timezone
from rest_framework.test import APIClient

from promociones.models import Promocion
from sedes.models import Ciudad, Sede
from usuarios.models import Empleado, Usuario
from usuarios.roles import ADMINISTRADOR, COCINA, OPERADOR, REPARTIDOR

URL = "/api/promociones/"

pytestmark = pytest.mark.django_db


def _sede(nombre="Centro"):
    ciudad, _ = Ciudad.objects.get_or_create(nombre="Cali")
    return Sede.objects.create(
        ciudad=ciudad, nombre=nombre, direccion="Calle 1 # 2-3", latitud=3.45,
        longitud=-76.53, barrio="Granada", telefono="3000000000", correo="s@correo.com",
    )


def _personal(rol, email, sede):
    usuario = Usuario.objects.create_user(username=email, email=email, password="ClaveSegura2026")
    usuario.groups.add(Group.objects.get_or_create(name=rol)[0])
    Empleado.objects.create(
        usuario=usuario, sede=sede, tipo_documento="CC", num_documento=email[:10],
        nombres="N", apellidos="A", celular="3001234567", direccion="Calle 4",
    )
    return usuario


def _api(usuario=None):
    cliente = APIClient()
    if usuario is not None:
        cliente.force_authenticate(usuario)
    return cliente


def _datos(**cambios):
    hoy = timezone.localdate()
    base = {
        "nombre": "Martes de combos",
        "descripcion": "Descuento entre semana",
        "tipo_descuento": "porcentaje",
        "valor": "15.00",
        "fecha_inicio": str(hoy),
        "fecha_fin": str(hoy + timedelta(days=7)),
        "condiciones": "Solo domicilios",
    }
    base.update(cambios)
    return base


def _promocion(sede, nombre="Promo", dias_inicio=0, dias_fin=7, **cambios):
    hoy = timezone.localdate()
    datos = {
        "sede": sede, "nombre": nombre, "tipo_descuento": "porcentaje", "valor": 10,
        "fecha_inicio": hoy + timedelta(days=dias_inicio),
        "fecha_fin": hoy + timedelta(days=dias_fin),
    }
    datos.update(cambios)
    return Promocion.objects.create(**datos)


@pytest.fixture
def sede():
    return _sede()


@pytest.fixture
def operador(sede):
    return _personal(OPERADOR, "operador@correo.com", sede)


# --- Criterio 1: crear con nombre, tipo, vigencia y condiciones --------------------


def test_el_operador_crea_una_promocion_en_su_sede(operador, sede):
    respuesta = _api(operador).post(URL, _datos(), format="json")

    assert respuesta.status_code == 201
    cuerpo = respuesta.json()
    assert cuerpo["sede"] == sede.pk
    assert cuerpo["nombre"] == "Martes de combos"
    assert cuerpo["tipo_descuento"] == "porcentaje"
    assert cuerpo["valor"] == "15.00"
    assert cuerpo["condiciones"] == "Solo domicilios"
    assert cuerpo["activa"] is True
    assert Promocion.objects.get(pk=cuerpo["id"]).sede == sede


def test_el_operador_no_puede_crear_en_otra_sede(operador, sede):
    otra = _sede("Norte")

    respuesta = _api(operador).post(URL, _datos(sede=otra.pk), format="json")

    assert respuesta.status_code == 201
    assert respuesta.json()["sede"] == sede.pk


def test_se_crea_con_descuento_de_valor_fijo(operador):
    respuesta = _api(operador).post(
        URL, _datos(tipo_descuento="valor_fijo", valor="5000"), format="json"
    )

    assert respuesta.status_code == 201
    assert respuesta.json()["valor"] == "5000.00"


def test_el_administrador_debe_elegir_la_sede():
    admin = _personal(ADMINISTRADOR, "admin@correo.com", None)
    sede_norte = _sede("Norte")

    sin_sede = _api(admin).post(URL, _datos(), format="json")
    con_sede = _api(admin).post(URL, _datos(sede=sede_norte.pk), format="json")

    assert sin_sede.status_code == 400
    assert "sede" in sin_sede.json()
    assert con_sede.status_code == 201
    assert con_sede.json()["sede"] == sede_norte.pk


def test_campos_obligatorios(operador):
    for campo in ("nombre", "tipo_descuento", "valor", "fecha_inicio", "fecha_fin"):
        datos = _datos()
        datos.pop(campo)
        respuesta = _api(operador).post(URL, datos, format="json")
        assert respuesta.status_code == 400, campo
        assert campo in respuesta.json(), campo


def test_tipo_de_descuento_invalido(operador):
    respuesta = _api(operador).post(URL, _datos(tipo_descuento="regalo"), format="json")
    assert respuesta.status_code == 400
    assert "tipo_descuento" in respuesta.json()


def test_nombre_repetido_en_la_misma_sede_pero_no_en_otra(operador, sede):
    _promocion(sede, nombre="Martes de combos")
    otra = _sede("Norte")
    _promocion(otra, nombre="Solo norte")

    repetido = _api(operador).post(URL, _datos(nombre="martes DE combos"), format="json")
    admin = _personal(ADMINISTRADOR, "admin@correo.com", None)
    en_otra_sede = _api(admin).post(
        URL, _datos(nombre="Martes de combos", sede=otra.pk), format="json"
    )

    assert repetido.status_code == 400
    assert "nombre" in repetido.json()
    assert en_otra_sede.status_code == 201


# --- Criterio 2: el formulario rechaza fechas y descuentos inválidos ----------------


def test_fecha_de_fin_anterior_al_inicio_es_rechazada(operador):
    hoy = timezone.localdate()
    respuesta = _api(operador).post(
        URL,
        _datos(fecha_inicio=str(hoy), fecha_fin=str(hoy - timedelta(days=1))),
        format="json",
    )

    assert respuesta.status_code == 400
    assert "fecha_fin" in respuesta.json()
    assert Promocion.objects.count() == 0


def test_una_promocion_de_un_solo_dia_es_valida(operador):
    hoy = str(timezone.localdate())
    respuesta = _api(operador).post(URL, _datos(fecha_inicio=hoy, fecha_fin=hoy), format="json")
    assert respuesta.status_code == 201


@pytest.mark.parametrize("valor", ["100.01", "101", "250"])
def test_un_porcentaje_mayor_que_100_es_rechazado(operador, valor):
    respuesta = _api(operador).post(URL, _datos(valor=valor), format="json")
    assert respuesta.status_code == 400
    assert "valor" in respuesta.json()


def test_un_porcentaje_de_exactamente_100_es_valido(operador):
    assert _api(operador).post(URL, _datos(valor="100"), format="json").status_code == 201


@pytest.mark.parametrize("tipo", ["porcentaje", "valor_fijo"])
@pytest.mark.parametrize("valor", ["0", "-5", "-0.01"])
def test_un_descuento_menor_o_igual_a_cero_es_rechazado(operador, tipo, valor):
    respuesta = _api(operador).post(URL, _datos(tipo_descuento=tipo, valor=valor), format="json")
    assert respuesta.status_code == 400
    assert "valor" in respuesta.json()


def test_un_valor_fijo_puede_superar_100(operador):
    respuesta = _api(operador).post(
        URL, _datos(tipo_descuento="valor_fijo", valor="12000"), format="json"
    )
    assert respuesta.status_code == 201


# --- Editar -------------------------------------------------------------------------


def test_editar_una_promocion(operador, sede):
    promocion = _promocion(sede, nombre="Vieja")

    respuesta = _api(operador).patch(
        f"{URL}{promocion.pk}/",
        {"nombre": "Nueva", "valor": "20", "condiciones": "Pedido mínimo $30.000"},
        format="json",
    )

    assert respuesta.status_code == 200
    promocion.refresh_from_db()
    assert promocion.nombre == "Nueva"
    assert promocion.valor == 20
    assert promocion.condiciones == "Pedido mínimo $30.000"


def test_al_editar_se_siguen_validando_las_reglas_con_los_valores_guardados(operador, sede):
    promocion = _promocion(sede, tipo_descuento="porcentaje", valor=10, dias_inicio=0, dias_fin=5)
    hoy = timezone.localdate()

    fecha = _api(operador).patch(
        f"{URL}{promocion.pk}/", {"fecha_fin": str(hoy - timedelta(days=1))}, format="json"
    )
    porcentaje = _api(operador).patch(f"{URL}{promocion.pk}/", {"valor": "150"}, format="json")
    cambio_de_tipo = _api(operador).patch(
        f"{URL}{promocion.pk}/", {"tipo_descuento": "valor_fijo", "valor": "150"}, format="json"
    )

    assert fecha.status_code == 400 and "fecha_fin" in fecha.json()
    assert porcentaje.status_code == 400 and "valor" in porcentaje.json()
    assert cambio_de_tipo.status_code == 200


def test_editar_el_nombre_no_choca_consigo_misma(operador, sede):
    promocion = _promocion(sede, nombre="Igual")
    respuesta = _api(operador).patch(
        f"{URL}{promocion.pk}/", {"nombre": "Igual", "valor": "12"}, format="json"
    )
    assert respuesta.status_code == 200


def test_no_se_puede_mover_una_promocion_a_otra_sede(operador, sede):
    promocion = _promocion(sede)
    otra = _sede("Norte")

    respuesta = _api(operador).patch(f"{URL}{promocion.pk}/", {"sede": otra.pk}, format="json")

    assert respuesta.status_code == 400
    assert "sede" in respuesta.json()


# --- Criterio 4: desactivar conserva el historial y deja de poder usarse ---------------


def test_eliminar_desactiva_y_conserva_la_promocion(operador, sede):
    promocion = _promocion(sede)

    respuesta = _api(operador).delete(f"{URL}{promocion.pk}/")

    assert respuesta.status_code == 204
    promocion.refresh_from_db()
    assert promocion.activa is False
    assert promocion.utilizable() is False
    inactivas = _api(operador).get(URL, {"activa": "false"}).json()
    assert [item["id"] for item in inactivas] == [promocion.pk]


def test_una_promocion_desactivada_se_puede_reactivar(operador, sede):
    promocion = _promocion(sede, activa=False)

    respuesta = _api(operador).patch(f"{URL}{promocion.pk}/", {"activa": True}, format="json")

    assert respuesta.status_code == 200
    assert respuesta.json()["utilizable"] is True


def test_estado_segun_actividad_y_vigencia(sede):
    vigente = _promocion(sede, "Vigente", dias_inicio=-1, dias_fin=1)
    programada = _promocion(sede, "Programada", dias_inicio=2, dias_fin=5)
    vencida = _promocion(sede, "Vencida", dias_inicio=-10, dias_fin=-1)
    inactiva = _promocion(sede, "Inactiva", activa=False)
    vencida_e_inactiva = _promocion(sede, "Ambas", dias_inicio=-10, dias_fin=-1, activa=False)

    assert vigente.estado() == "vigente" and vigente.utilizable()
    assert programada.estado() == "programada" and not programada.utilizable()
    assert vencida.estado() == "vencida" and not vencida.utilizable()
    assert inactiva.estado() == "inactiva" and not inactiva.utilizable()
    assert vencida_e_inactiva.estado() == "inactiva"
    # Solo la vigente se puede aplicar a una compra.
    assert list(Promocion.objects.utilizables()) == [vigente]


def test_el_primer_y_el_ultimo_dia_de_la_vigencia_son_utilizables(sede):
    hoy = timezone.localdate()
    promocion = _promocion(sede, dias_inicio=0, dias_fin=3)

    assert promocion.utilizable(hoy)
    assert promocion.utilizable(hoy + timedelta(days=3))
    assert not promocion.utilizable(hoy + timedelta(days=4))
    assert not promocion.utilizable(hoy - timedelta(days=1))


def test_el_listado_trae_estado_y_se_filtra_por_estado(operador, sede):
    _promocion(sede, "Vigente", dias_inicio=-1, dias_fin=1)
    _promocion(sede, "Programada", dias_inicio=2, dias_fin=5)
    _promocion(sede, "Vencida", dias_inicio=-10, dias_fin=-1)
    _promocion(sede, "Inactiva", activa=False)
    cliente = _api(operador)

    todas = cliente.get(URL).json()
    assert {item["nombre"]: item["estado"] for item in todas} == {
        "Vigente": "vigente", "Programada": "programada",
        "Vencida": "vencida", "Inactiva": "inactiva",
    }
    for estado, nombre in (
        ("vigente", "Vigente"), ("programada", "Programada"),
        ("vencida", "Vencida"), ("inactiva", "Inactiva"),
    ):
        filtradas = cliente.get(URL, {"estado": estado}).json()
        assert [item["nombre"] for item in filtradas] == [nombre]
    assert cliente.get(URL, {"estado": "raro"}).json() == []


# --- Sedes y permisos ---------------------------------------------------------------


def test_el_operador_solo_ve_y_toca_las_promociones_de_su_sede(operador, sede):
    otra = _sede("Norte")
    propia = _promocion(sede, "Propia")
    ajena = _promocion(otra, "Ajena")
    cliente = _api(operador)

    assert [item["id"] for item in cliente.get(URL).json()] == [propia.pk]
    assert cliente.get(f"{URL}{ajena.pk}/").status_code == 404
    assert cliente.patch(f"{URL}{ajena.pk}/", {"valor": "5"}, format="json").status_code == 404
    assert cliente.delete(f"{URL}{ajena.pk}/").status_code == 404
    ajena.refresh_from_db()
    assert ajena.activa is True and ajena.valor == 10


def test_el_administrador_ve_las_de_todas_las_sedes(sede):
    otra = _sede("Norte")
    _promocion(sede, "Una")
    _promocion(otra, "Otra")
    admin = _personal(ADMINISTRADOR, "admin@correo.com", None)

    assert len(_api(admin).get(URL).json()) == 2


def test_un_operador_sin_sede_no_puede_crear(sede):
    sin_sede = _personal(OPERADOR, "sinsede@correo.com", None)

    respuesta = _api(sin_sede).post(URL, _datos(), format="json")

    assert respuesta.status_code == 400
    assert "sede" in respuesta.json()


def test_otros_roles_y_anonimos_no_tienen_acceso(sede):
    cocina = _personal(COCINA, "cocina@correo.com", sede)
    repartidor = _personal(REPARTIDOR, "repartidor@correo.com", sede)
    cliente_sin_rol = Usuario.objects.create_user(
        username="cli@correo.com", email="cli@correo.com", password="ClaveSegura2026"
    )

    assert _api().get(URL).status_code in (401, 403)
    for usuario in (cocina, repartidor, cliente_sin_rol):
        assert _api(usuario).get(URL).status_code == 403
        assert _api(usuario).post(URL, _datos(), format="json").status_code == 403