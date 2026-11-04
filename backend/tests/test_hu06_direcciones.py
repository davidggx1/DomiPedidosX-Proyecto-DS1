"""HU-06 · Direcciones de entrega: coordenadas obligatorias, edición, borrado y acceso ajeno."""
import pytest
from django.contrib.auth.models import Group
from rest_framework.test import APIClient

from pedidos.models import Pedido
from sedes.models import Ciudad, Sede
from usuarios.models import Cliente, DireccionEntrega, Empleado, Usuario

URL = "/api/usuarios/direcciones/"


def crear_cliente(correo, documento, celular):
    usuario = Usuario.objects.create_user(username=correo, email=correo, password="ClaveSegura2026")
    return Cliente.objects.create(
        usuario=usuario, tipo_documento="CC", num_documento=documento,
        nombres="Ana", apellidos="Pérez", celular=celular, fecha_nacimiento="2000-01-01",
    )


def api_de(usuario=None):
    api = APIClient()
    if usuario:
        api.force_authenticate(user=usuario)
    return api


def url(direccion):
    return f"{URL}{direccion.id}/"


def datos(**cambios):
    base = {
        "alias": "Casa", "direccion": "Calle 5 # 38-20", "barrio": "San Fernando",
        "latitud": 3.4372, "longitud": -76.5410,
    }
    base.update(cambios)
    return base


@pytest.fixture
def ciudad(db):
    return Ciudad.objects.create(nombre="Cali")


@pytest.fixture
def ana(ciudad):
    return crear_cliente("ana@correo.com", "100", "3000000001")


@pytest.fixture
def luis(ciudad):
    return crear_cliente("luis@correo.com", "200", "3000000002")


@pytest.fixture
def api_ana(ana):
    return api_de(ana.usuario)


def crear_direccion(cliente, **cambios):
    valores = datos(**cambios)
    return DireccionEntrega.objects.create(
        cliente=cliente, ciudad=Ciudad.objects.first(), **valores
    )


# --- Crear y coordenadas obligatorias ----------------------------------------


def test_crear_direccion_con_coordenadas(api_ana, ana):
    respuesta = api_ana.post(URL, datos(), format="json")

    assert respuesta.status_code == 201
    direccion = DireccionEntrega.objects.get(pk=respuesta.data["id"])
    assert direccion.cliente == ana
    assert direccion.ciudad.nombre == "Cali"
    assert (direccion.latitud, direccion.longitud) == (3.4372, -76.5410)


@pytest.mark.parametrize("campo", ["latitud", "longitud"])
def test_rechaza_direccion_sin_coordenadas(api_ana, campo):
    cuerpo = datos()
    del cuerpo[campo]

    respuesta = api_ana.post(URL, cuerpo, format="json")

    assert respuesta.status_code == 400
    assert campo in respuesta.data
    assert not DireccionEntrega.objects.exists()


def test_rechaza_coordenadas_nulas(api_ana):
    respuesta = api_ana.post(URL, datos(latitud=None, longitud=None), format="json")

    assert respuesta.status_code == 400
    assert {"latitud", "longitud"} <= set(respuesta.data)


@pytest.mark.parametrize("cambio", [{"latitud": 91}, {"latitud": -91}, {"longitud": 181}, {"longitud": -181}])
def test_rechaza_coordenadas_fuera_de_rango(api_ana, cambio):
    respuesta = api_ana.post(URL, datos(**cambio), format="json")

    assert respuesta.status_code == 400


def test_alias_es_obligatorio_y_barrio_opcional(api_ana):
    sin_alias = datos()
    del sin_alias["alias"]
    assert api_ana.post(URL, sin_alias, format="json").status_code == 400

    sin_barrio = datos()
    del sin_barrio["barrio"]
    assert api_ana.post(URL, sin_barrio, format="json").status_code == 201


# --- Listar ------------------------------------------------------------------


def test_listado_muestra_solo_las_propias_y_activas(api_ana, ana, luis):
    propia = crear_direccion(ana, alias="Casa")
    crear_direccion(ana, alias="Vieja", activa=False)
    crear_direccion(luis, alias="De Luis")

    respuesta = api_ana.get(URL)

    assert respuesta.status_code == 200
    assert [d["id"] for d in respuesta.data] == [propia.id]


# --- Editar ------------------------------------------------------------------


def test_editar_direccion_propia(api_ana, ana):
    direccion = crear_direccion(ana)

    respuesta = api_ana.patch(
        url(direccion), {"alias": "Oficina", "latitud": 3.45, "longitud": -76.53}, format="json"
    )

    assert respuesta.status_code == 200
    direccion.refresh_from_db()
    assert (direccion.alias, direccion.latitud, direccion.longitud) == ("Oficina", 3.45, -76.53)


def test_editar_no_permite_quitar_coordenadas(api_ana, ana):
    direccion = crear_direccion(ana)

    respuesta = api_ana.patch(url(direccion), {"latitud": None}, format="json")

    assert respuesta.status_code == 400
    direccion.refresh_from_db()
    assert direccion.latitud == 3.4372


def test_nueva_principal_reemplaza_a_la_anterior(api_ana, ana):
    anterior = crear_direccion(ana, alias="Casa", es_principal=True)
    otra = crear_direccion(ana, alias="Oficina")

    respuesta = api_ana.patch(url(otra), {"es_principal": True}, format="json")

    assert respuesta.status_code == 200
    anterior.refresh_from_db()
    otra.refresh_from_db()
    assert not anterior.es_principal and otra.es_principal


def test_crear_como_principal_desmarca_la_anterior(api_ana, ana):
    anterior = crear_direccion(ana, es_principal=True)

    respuesta = api_ana.post(URL, datos(alias="Oficina", es_principal=True), format="json")

    assert respuesta.status_code == 201
    anterior.refresh_from_db()
    assert not anterior.es_principal


# --- Eliminar ----------------------------------------------------------------


def test_eliminar_es_borrado_logico(api_ana, ana):
    direccion = crear_direccion(ana, es_principal=True)

    respuesta = api_ana.delete(url(direccion))

    assert respuesta.status_code == 204
    assert api_ana.get(URL).data == []
    direccion.refresh_from_db()
    assert not direccion.activa and not direccion.es_principal


def test_tras_eliminar_la_principal_se_puede_marcar_otra(api_ana, ana):
    principal = crear_direccion(ana, es_principal=True)
    api_ana.delete(url(principal))

    respuesta = api_ana.post(URL, datos(alias="Nueva", es_principal=True), format="json")

    assert respuesta.status_code == 201


def test_direccion_eliminada_no_se_puede_editar(api_ana, ana):
    direccion = crear_direccion(ana, activa=False)

    assert api_ana.patch(url(direccion), {"alias": "X"}, format="json").status_code == 404


# --- Acceso a direcciones ajenas y permisos ----------------------------------


def test_no_puede_ver_editar_ni_eliminar_direccion_ajena(api_ana, luis):
    ajena = crear_direccion(luis, alias="De Luis")

    assert api_ana.get(url(ajena)).status_code == 404
    assert api_ana.patch(url(ajena), {"alias": "Mía"}, format="json").status_code == 404
    assert api_ana.delete(url(ajena)).status_code == 404
    ajena.refresh_from_db()
    assert ajena.alias == "De Luis" and ajena.activa


def test_sin_autenticacion_responde_401(db):
    assert api_de().get(URL).status_code == 401


def test_empleado_no_tiene_direcciones_de_cliente(ciudad):
    sede = Sede.objects.create(
        ciudad=ciudad, nombre="Centro", direccion="Cra 1 # 2-3", latitud=3.45,
        longitud=-76.53, barrio="Centro", telefono="3000000000", correo="centro@domi.com",
    )
    usuario = Usuario.objects.create_user(username="op@correo.com", email="op@correo.com", password="x")
    usuario.groups.add(Group.objects.get_or_create(name="operador")[0])
    Empleado.objects.create(
        usuario=usuario, sede=sede, tipo_documento="CC", num_documento="300",
        nombres="Op", apellidos="Uno", celular="3000000000", direccion="Calle 1",
    )

    assert api_de(usuario).get(URL).status_code == 403


# --- Pedidos ya realizados ---------------------------------------------------


@pytest.fixture
def pedido_con_direccion(ana, ciudad):
    sede = Sede.objects.create(
        ciudad=ciudad, nombre="Centro", direccion="Cra 1 # 2-3", latitud=3.45,
        longitud=-76.53, barrio="Centro", telefono="3000000000", correo="centro@domi.com",
    )
    direccion = crear_direccion(ana)
    pedido = Pedido(numero_pedido="P-001", sede=sede, cliente=ana)
    pedido.asignar_direccion_entrega(direccion)
    pedido.save()
    return pedido, direccion


def copia_de(pedido):
    pedido.refresh_from_db()
    return (
        pedido.entrega_alias, pedido.entrega_direccion, pedido.entrega_barrio,
        pedido.entrega_latitud, pedido.entrega_longitud,
    )


def test_pedido_copia_la_direccion(pedido_con_direccion):
    pedido, _ = pedido_con_direccion

    assert copia_de(pedido) == ("Casa", "Calle 5 # 38-20", "San Fernando", 3.4372, -76.5410)


def test_editar_direccion_no_altera_pedido_realizado(api_ana, pedido_con_direccion):
    pedido, direccion = pedido_con_direccion
    antes = copia_de(pedido)

    api_ana.patch(
        url(direccion),
        {"alias": "Oficina", "direccion": "Av. 6N # 20-10", "latitud": 3.46, "longitud": -76.52},
        format="json",
    )

    assert copia_de(pedido) == antes


def test_eliminar_direccion_no_altera_pedido_realizado(api_ana, pedido_con_direccion):
    pedido, direccion = pedido_con_direccion
    antes = copia_de(pedido)

    assert api_ana.delete(url(direccion)).status_code == 204

    assert copia_de(pedido) == antes
    assert pedido.direccion_entrega_id == direccion.id
