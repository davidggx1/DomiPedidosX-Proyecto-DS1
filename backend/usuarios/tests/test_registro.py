import pytest
from rest_framework.test import APIClient

from usuarios.models import Cliente, Usuario

URL = "/api/usuarios/registro/"

DATOS_VALIDOS = {
    "email": "ana@correo.com",
    "password": "ClaveSegura2026",
    "tipo_documento": "CC",
    "num_documento": "1234567890",
    "nombres": "Ana",
    "apellidos": "Prueba",
    "celular": "3001234567",
    "fecha_nacimiento": "2000-05-20",
}


@pytest.fixture
def client():
    return APIClient()


@pytest.mark.django_db
def test_registro_valido_crea_usuario_y_cliente(client):
    response = client.post(URL, DATOS_VALIDOS, format="json")
    assert response.status_code == 201
    usuario = Usuario.objects.get(email="ana@correo.com")
    assert Cliente.objects.filter(usuario=usuario).exists()


@pytest.mark.django_db
def test_contrasena_se_guarda_cifrada(client):
    client.post(URL, DATOS_VALIDOS, format="json")
    usuario = Usuario.objects.get(email="ana@correo.com")
    assert usuario.password != DATOS_VALIDOS["password"]
    assert usuario.check_password(DATOS_VALIDOS["password"])


@pytest.mark.django_db
def test_correo_duplicado_es_rechazado(client):
    client.post(URL, DATOS_VALIDOS, format="json")
    otros = {**DATOS_VALIDOS, "num_documento": "9999999999"}
    response = client.post(URL, otros, format="json")
    assert response.status_code == 400
    assert "email" in response.data
    assert Usuario.objects.filter(email="ana@correo.com").count() == 1


@pytest.mark.django_db
def test_documento_duplicado_es_rechazado(client):
    client.post(URL, DATOS_VALIDOS, format="json")
    otros = {**DATOS_VALIDOS, "email": "otra@correo.com"}
    response = client.post(URL, otros, format="json")
    assert response.status_code == 400
    assert not Usuario.objects.filter(email="otra@correo.com").exists()


@pytest.mark.django_db
def test_correo_mal_formado(client):
    response = client.post(URL, {**DATOS_VALIDOS, "email": "abc"}, format="json")
    assert response.status_code == 400
    assert "email" in response.data


@pytest.mark.django_db
def test_contrasena_corta(client):
    response = client.post(URL, {**DATOS_VALIDOS, "password": "123"}, format="json")
    assert response.status_code == 400
    assert "password" in response.data


@pytest.mark.django_db
def test_campo_obligatorio_vacio(client):
    datos = {**DATOS_VALIDOS, "nombres": ""}
    response = client.post(URL, datos, format="json")
    assert response.status_code == 400
    assert "nombres" in response.data