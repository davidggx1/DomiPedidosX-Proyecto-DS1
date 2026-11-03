import pytest
from django.contrib.auth.models import Group
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.test import APIClient, APIRequestFactory, force_authenticate
from rest_framework.views import APIView

from sedes.models import Ciudad, Sede
from usuarios.models import Empleado, Usuario
from usuarios.permissions import filtrar_por_sede, rol_requerido
from usuarios.roles import ADMINISTRADOR, COCINA, OPERADOR, REPARTIDOR

LOGIN = "/api/usuarios/login-personal/"
PERFIL = "/api/usuarios/perfil-personal/"
PASSWORD = "ClaveSegura2026"


@pytest.fixture
def client():
    return APIClient()


@pytest.fixture
def sede(db):
    ciudad = Ciudad.objects.create(nombre="Cali")
    return Sede.objects.create(
        ciudad=ciudad, nombre="Sede Norte", direccion="Calle 1 # 2-3",
        latitud=3.45, longitud=-76.53, barrio="Granada",
        telefono="3000000000", correo="norte@correo.com",
    )


@pytest.fixture
def crear_personal(db, sede):
    def _crear(rol, email, con_empleado=True, activo=True):
        usuario = Usuario.objects.create_user(
            username=email, email=email, password=PASSWORD, is_active=activo
        )
        usuario.groups.add(Group.objects.get_or_create(name=rol)[0])
        if con_empleado:
            Empleado.objects.create(
                usuario=usuario, sede=sede, tipo_documento="CC",
                num_documento=email[:10], nombres="Nombre", apellidos="Apellido",
                celular="3001234567", direccion="Calle 4",
            )
        return usuario
    return _crear


def login(client, email, password=PASSWORD):
    return client.post(LOGIN, {"email": email, "password": password}, format="json")


@pytest.mark.parametrize("rol", [OPERADOR, COCINA, REPARTIDOR])
def test_personal_inicia_sesion_y_recibe_rol_y_sede(client, crear_personal, sede, rol):
    crear_personal(rol, f"{rol}@correo.com")
    response = login(client, f"{rol}@correo.com")
    assert response.status_code == 200
    assert response.data["rol"] == rol
    assert response.data["sede_id"] == sede.pk


def test_administrador_entra_sin_sede(client, crear_personal):
    crear_personal(ADMINISTRADOR, "admin@correo.com", con_empleado=False)
    response = login(client, "admin@correo.com")
    assert response.status_code == 200
    assert response.data["rol"] == ADMINISTRADOR
    assert response.data["sede_id"] is None


def test_cliente_no_puede_entrar_por_login_de_personal(client, db):
    Usuario.objects.create_user(username="c@correo.com", email="c@correo.com", password=PASSWORD)
    assert login(client, "c@correo.com").status_code == 401


def test_empleado_sin_sede_es_rechazado(client, crear_personal):
    crear_personal(OPERADOR, "sinsede@correo.com", con_empleado=False)
    assert login(client, "sinsede@correo.com").status_code == 401


def test_credenciales_invalidas(client, crear_personal):
    crear_personal(OPERADOR, "op@correo.com")
    assert login(client, "op@correo.com", "incorrecta").status_code == 401


def test_cuenta_desactivada_es_rechazada(client, crear_personal):
    crear_personal(OPERADOR, "op@correo.com", activo=False)
    response = login(client, "op@correo.com")
    assert response.status_code == 401
    assert "access" not in response.data


def test_perfil_personal_con_token(client, crear_personal, sede):
    crear_personal(COCINA, "cocina@correo.com")
    token = login(client, "cocina@correo.com").data["access"]
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
    response = client.get(PERFIL)
    assert response.status_code == 200
    assert response.data["rol"] == COCINA
    assert response.data["sede_id"] == sede.pk


def test_endpoint_protegido_sin_token_responde_401(client):
    assert client.get(PERFIL).status_code == 401


def test_cliente_no_accede_al_perfil_de_personal(client, db):
    Usuario.objects.create_user(username="c@correo.com", email="c@correo.com", password=PASSWORD)
    token = client.post(
        "/api/usuarios/login/", {"email": "c@correo.com", "password": PASSWORD}, format="json"
    ).data["access"]
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
    assert client.get(PERFIL).status_code == 403


def test_rol_no_puede_abrir_funcion_de_otro_rol(crear_personal):
    class SoloAdmin(APIView):
        permission_classes = [rol_requerido(ADMINISTRADOR)]

        def get(self, request):
            return Response({"ok": True})

    operador = crear_personal(OPERADOR, "op@correo.com")
    admin = crear_personal(ADMINISTRADOR, "admin@correo.com", con_empleado=False)
    factory = APIRequestFactory()

    request = factory.get("/x/")
    force_authenticate(request, user=operador)
    assert SoloAdmin.as_view()(request).status_code == 403

    request = factory.get("/x/")
    force_authenticate(request, user=admin)
    assert SoloAdmin.as_view()(request).status_code == 200


def test_filtrar_por_sede_limita_al_personal_y_no_al_admin(crear_personal, sede):
    operador = crear_personal(OPERADOR, "op@correo.com")
    admin = crear_personal(ADMINISTRADOR, "admin@correo.com", con_empleado=False)
    empleados = Empleado.objects.all()
    assert set(filtrar_por_sede(empleados, operador)) == set(empleados.filter(sede=sede))
    assert filtrar_por_sede(empleados, admin).count() == empleados.count()