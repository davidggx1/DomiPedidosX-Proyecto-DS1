"""Pruebas de HU-80 · Editar y reactivar cuentas del personal."""
import pytest
from django.contrib.auth.models import Group
from rest_framework.test import APIClient

from pedidos.models import EstadoPedido, Pedido
from sedes.models import Ciudad, Sede
from usuarios.models import Empleado, Repartidor, Usuario
from usuarios.roles import ADMINISTRADOR, COCINA, OPERADOR, REPARTIDOR

pytestmark = pytest.mark.django_db

CLAVE = "ClaveSegura2026"
LOGIN = "/api/usuarios/login-personal/"
EMPLEADOS = "/api/usuarios/empleados/"
PROMOCIONES = "/api/promociones/"  # solo operador y administrador


def url(empleado):
    return f"{EMPLEADOS}{empleado.pk}/"


def _sede(nombre="Centro", activa=True):
    ciudad, _ = Ciudad.objects.get_or_create(nombre="Cali")
    return Sede.objects.create(
        ciudad=ciudad, nombre=nombre, direccion="Calle 1 # 2-3", latitud=3.45, longitud=-76.53,
        barrio="Centro", telefono="3000000000", correo="s@correo.com", activa=activa,
    )


def _personal(rol, email, sede=None, grupo=None, documento=None):
    usuario = Usuario.objects.create_user(
        username=email, email=email, password=CLAVE, is_staff=(rol == ADMINISTRADOR)
    )
    usuario.groups.add(Group.objects.get_or_create(name=grupo or rol)[0])
    empleado = Empleado.objects.create(
        usuario=usuario, sede=sede, tipo_documento="CC", num_documento=documento or email[:10],
        nombres="Nombre", apellidos="Apellido", celular="3001234567", direccion="Calle 4",
    )
    if rol == REPARTIDOR:
        Repartidor.objects.create(empleado=empleado, disponible=True)
    return empleado


def _api(usuario=None):
    api = APIClient()
    if usuario is not None:
        api.force_authenticate(usuario)
    return api


def _login(email):
    return APIClient().post(LOGIN, {"email": email, "password": CLAVE}, format="json")


@pytest.fixture
def sede():
    return _sede()


@pytest.fixture
def admin():
    return _personal(ADMINISTRADOR, "admin@correo.com")


@pytest.fixture
def operador(sede):
    return _personal(OPERADOR, "operador@correo.com", sede)


def editar(admin, empleado, **datos):
    return _api(admin.usuario).patch(url(empleado), datos, format="json")


# --- Criterio 1: modificar nombre, rol o sede de una cuenta activa o inactiva ---------


def test_el_admin_consulta_el_detalle(admin, operador):
    datos = _api(admin.usuario).get(url(operador)).data
    assert datos["email"] == "operador@correo.com"
    assert datos["rol"] == "OPERADOR" and datos["activa"] is True
    assert datos["sede"] == "Centro" and datos["num_documento"]


def test_edita_nombres_celular_y_direccion(admin, operador):
    respuesta = editar(admin, operador, nombres="Luisa", apellidos="Mora", celular="3109998877",
                       direccion="Carrera 9 # 8-7")
    assert respuesta.status_code == 200
    operador.refresh_from_db()
    assert (operador.nombres, operador.apellidos, operador.celular) == ("Luisa", "Mora", "3109998877")
    assert operador.direccion == "Carrera 9 # 8-7"


def test_edita_una_cuenta_inactiva(admin, operador):
    operador.usuario.is_active = False
    operador.usuario.save()
    respuesta = editar(admin, operador, nombres="Luisa")
    assert respuesta.status_code == 200
    assert respuesta.data["activa"] is False and respuesta.data["nombres"] == "Luisa"


def test_cambia_el_rol_y_reemplaza_el_grupo(admin, operador):
    respuesta = editar(admin, operador, rol="COCINA")
    assert respuesta.status_code == 200 and respuesta.data["rol"] == "COCINA"
    grupos = set(operador.usuario.groups.values_list("name", flat=True))
    assert grupos == {COCINA}


def test_reemplaza_tambien_grupos_en_mayusculas(admin, sede):
    viejo = _personal(OPERADOR, "viejo@correo.com", sede, grupo="OPERADOR")
    editar(admin, viejo, rol="COCINA")
    assert set(viejo.usuario.groups.values_list("name", flat=True)) == {COCINA}


def test_cambia_la_sede(admin, operador):
    norte = _sede("Norte")
    respuesta = editar(admin, operador, sede_id=norte.pk)
    assert respuesta.status_code == 200 and respuesta.data["sede"] == "Norte"
    operador.refresh_from_db()
    assert operador.sede == norte


def test_ascender_a_administrador_no_pide_sede_y_da_acceso_staff(admin, operador):
    assert editar(admin, operador, rol="ADMINISTRADOR").status_code == 200
    operador.refresh_from_db()
    assert operador.sede is None and operador.usuario.is_staff is True


def test_un_rol_operativo_exige_sede(admin, operador):
    assert editar(admin, operador, sede_id=None).status_code == 400
    assert "sede_id" in editar(admin, operador, sede_id=None).data


def test_rechaza_sede_inactiva_o_inexistente(admin, operador):
    cerrada = _sede("Cerrada", activa=False)
    assert editar(admin, operador, sede_id=cerrada.pk).status_code == 400
    assert editar(admin, operador, sede_id=9999).status_code == 400


def test_rechaza_rol_invalido_celular_invalido_y_nombre_vacio(admin, operador):
    assert editar(admin, operador, rol="CLIENTE").status_code == 400
    assert editar(admin, operador, celular="123").status_code == 400
    assert editar(admin, operador, nombres="  ").status_code == 400


def test_documento_repetido_se_rechaza_pero_el_propio_no(admin, operador, sede):
    otro = _personal(COCINA, "cocina@correo.com", sede, documento="999")
    assert editar(admin, operador, num_documento="999").status_code == 400
    propio = editar(admin, operador, num_documento=operador.num_documento, nombres="Ana")
    assert propio.status_code == 200


def test_el_correo_no_se_modifica(admin, operador):
    editar(admin, operador, email="otro@correo.com", nombres="Ana")
    operador.usuario.refresh_from_db()
    assert operador.usuario.email == "operador@correo.com"


def test_put_exige_los_datos_y_patch_acepta_parciales(admin, operador):
    assert _api(admin.usuario).put(url(operador), {"nombres": "Ana"}, format="json").status_code == 400
    completo = {
        "nombres": "Ana", "apellidos": "Mora", "tipo_documento": "CC",
        "num_documento": operador.num_documento, "celular": "3001112233", "direccion": "Calle 1",
    }
    assert _api(admin.usuario).put(url(operador), completo, format="json").status_code == 200


# --- Criterio 2: el usuario ve sus nuevos permisos al iniciar sesión -------------------


def test_el_login_devuelve_el_rol_y_la_sede_nuevos(admin, operador):
    assert _login("operador@correo.com").data["rol"] == "operador"
    norte = _sede("Norte")
    editar(admin, operador, rol="COCINA", sede_id=norte.pk)
    datos = _login("operador@correo.com").data
    assert datos["rol"] == "cocina" and datos["sede_id"] == norte.pk


def test_el_permiso_nuevo_vale_incluso_con_un_token_anterior(admin, operador):
    api = APIClient()
    token = _login("operador@correo.com").data["access"]
    api.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
    assert api.get(PROMOCIONES).status_code == 200  # operador
    editar(admin, operador, rol="COCINA")
    assert api.get(PROMOCIONES).status_code == 403  # ya no es operador


# --- Criterio 3: reactivar permite volver a autenticarse -------------------------------


def test_desactivar_y_reactivar_controla_el_login(admin, operador):
    assert editar(admin, operador, activa=False).status_code == 200
    assert _login("operador@correo.com").status_code == 401
    respuesta = editar(admin, operador, activa=True)
    assert respuesta.status_code == 200 and respuesta.data["activa"] is True
    assert _login("operador@correo.com").status_code == 200


def test_se_puede_reactivar_y_cambiar_rol_en_la_misma_peticion(admin, operador):
    editar(admin, operador, activa=False)
    editar(admin, operador, activa=True, rol="COCINA")
    assert _login("operador@correo.com").data["rol"] == "cocina"


def test_desactivar_un_repartidor_lo_deja_no_disponible(admin, sede):
    repa = _personal(REPARTIDOR, "repa@correo.com", sede)
    editar(admin, repa, activa=False)
    repa.perfil_repartidor.refresh_from_db()
    assert repa.perfil_repartidor.disponible is False


# --- Repartidores ------------------------------------------------------------------------


def test_pasar_a_repartidor_crea_su_perfil_no_disponible(admin, operador):
    editar(admin, operador, rol="REPARTIDOR")
    perfil = Repartidor.objects.get(empleado=operador)
    assert perfil.disponible is False


def test_dejar_de_ser_repartidor_lo_deja_no_disponible_y_conserva_el_perfil(admin, sede):
    repa = _personal(REPARTIDOR, "repa@correo.com", sede)
    assert editar(admin, repa, rol="COCINA").status_code == 200
    perfil = Repartidor.objects.get(empleado=repa)  # se conserva por los pedidos antiguos
    assert perfil.disponible is False


def test_repartidor_con_entrega_en_curso_no_cambia_de_rol_ni_de_sede(admin, sede):
    repa = _personal(REPARTIDOR, "repa@correo.com", sede)
    pedido = Pedido.objects.create(
        numero_pedido="P-1", sede=sede, repartidor=repa.perfil_repartidor, estado=EstadoPedido.EN_CAMINO
    )
    assert editar(admin, repa, rol="COCINA").status_code == 400
    assert editar(admin, repa, sede_id=_sede("Norte").pk).status_code == 400
    assert editar(admin, repa, nombres="Ana").status_code == 200  # los datos sí
    pedido.estado = EstadoPedido.ENTREGADO
    pedido.save()
    assert editar(admin, repa, rol="COCINA").status_code == 200


# --- Protecciones y permisos --------------------------------------------------------------


def test_el_admin_no_puede_cambiar_su_propio_rol_ni_desactivarse(admin):
    assert editar(admin, admin, rol="OPERADOR", sede_id=_sede().pk).status_code == 400
    assert editar(admin, admin, activa=False).status_code == 400
    admin.usuario.refresh_from_db()
    assert admin.usuario.is_active is True
    assert editar(admin, admin, nombres="Yo").status_code == 200  # sus datos sí


def test_otro_administrador_si_puede_editar_a_un_admin(admin):
    otro = _personal(ADMINISTRADOR, "admin2@correo.com")
    assert editar(admin, otro, nombres="Beto").status_code == 200


def test_solo_el_administrador_edita(operador, sede):
    cocina = _personal(COCINA, "cocina@correo.com", sede)
    assert _api(operador.usuario).patch(url(cocina), {"nombres": "X"}, format="json").status_code == 403
    assert _api(cocina.usuario).get(url(cocina)).status_code == 403
    assert _api().patch(url(cocina), {"nombres": "X"}, format="json").status_code == 401


def test_empleado_inexistente_responde_404(admin):
    assert _api(admin.usuario).patch(f"{EMPLEADOS}9999/", {"nombres": "X"}, format="json").status_code == 404