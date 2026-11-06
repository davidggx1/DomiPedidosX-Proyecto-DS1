import pytest
from rest_framework.test import APIClient

from usuarios.models import Usuario

URL = "/api/usuarios/login/"
EMAIL = "ana@correo.com"
PASSWORD = "ClaveSegura2026"


@pytest.fixture
def client():
    return APIClient()


@pytest.fixture
def usuario(db):
    return Usuario.objects.create_user(username=EMAIL, email=EMAIL, password=PASSWORD)


def test_login_valido_devuelve_tokens(client, usuario):
    response = client.post(URL, {"email": EMAIL, "password": PASSWORD}, format="json")
    assert response.status_code == 200
    assert "access" in response.data
    assert "refresh" in response.data


def test_contrasena_incorrecta_mensaje_generico(client, usuario):
    response = client.post(URL, {"email": EMAIL, "password": "otra"}, format="json")
    assert response.status_code == 401
    assert "access" not in response.data


def test_correo_inexistente_mismo_mensaje_que_contrasena_incorrecta(client, usuario):
    mala_clave = client.post(URL, {"email": EMAIL, "password": "otra"}, format="json")
    sin_cuenta = client.post(
        URL, {"email": "nadie@correo.com", "password": "otra"}, format="json"
    )
    assert sin_cuenta.status_code == 401
    assert sin_cuenta.data["detail"] == mala_clave.data["detail"]


def test_cuenta_desactivada_es_rechazada_e_informa_inactiva(client, usuario):
    usuario.is_active = False
    usuario.save()
    response = client.post(URL, {"email": EMAIL, "password": PASSWORD}, format="json")
    assert response.status_code == 401
    assert "inactiva" in str(response.data["detail"])
    assert "access" not in response.data


def test_cuenta_desactivada_con_clave_incorrecta_no_revela_estado(client, usuario):
    usuario.is_active = False
    usuario.save()
    response = client.post(URL, {"email": EMAIL, "password": "otra"}, format="json")
    assert response.status_code == 401
    assert "inactiva" not in str(response.data["detail"])