import pytest
from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APIClient
from usuarios.models import Cliente, TipoDocumento

User = get_user_model()


@pytest.mark.django_db
class TestHU02ValidacionTelefono:

    @pytest.fixture(autouse=True)
    def setup(self):
        self.client = APIClient()
        self.usuario_base = User.objects.create_user(
            username="existente@domipedidos.com",
            email="existente@domipedidos.com",
            password="Password123!",
        )
        self.cliente_existente = Cliente.objects.create(
            usuario=self.usuario_base,
            tipo_documento=TipoDocumento.CC,
            num_documento="123456789",
            nombres="Carlos",
            apellidos="Pérez",
            celular="3001234567",
            fecha_nacimiento="1995-01-01",
        )

    def test_registro_celular_exitoso(self):
        """Un usuario puede registrarse con un teléfono válido de 10 dígitos."""
        payload = {
            "email": "nuevo@domipedidos.com",
            "password": "Password123!",
            "tipo_documento": "CC",
            "num_documento": "987654321",
            "nombres": "Ana",
            "apellidos": "Gómez",
            "celular": "3109876543",
            "fecha_nacimiento": "1998-05-20",
        }
        response = self.client.post("/api/usuarios/registro/", payload)
        assert response.status_code == status.HTTP_201_CREATED

    def test_rechazar_celular_con_letras(self):
        """QA: Debe rechazar el registro si el celular contiene caracteres no numéricos."""
        payload = {
            "email": "letras@domipedidos.com",
            "password": "Password123!",
            "tipo_documento": "CC",
            "num_documento": "111222333",
            "nombres": "Pedro",
            "apellidos": "Rojas",
            "celular": "300123456a",
            "fecha_nacimiento": "1992-03-10",
        }
        response = self.client.post("/api/usuarios/registro/", payload)
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "celular" in response.data

    def test_rechazar_longitud_incorrecta(self):
        """QA: Debe rechazar si tiene menos o más de 10 dígitos."""
        # Menos de 10 dígitos
        payload_corto = {
            "email": "corto@test.com",
            "password": "Password123!",
            "tipo_documento": "CC",
            "num_documento": "444555666",
            "nombres": "Luis",
            "apellidos": "Silva",
            "celular": "300123",
            "fecha_nacimiento": "1990-01-01",
        }
        res_corto = self.client.post("/api/usuarios/registro/", payload_corto)
        assert res_corto.status_code == status.HTTP_400_BAD_REQUEST

        # Más de 10 dígitos
        payload_largo = {
            "email": "largo@test.com",
            "password": "Password123!",
            "tipo_documento": "CC",
            "num_documento": "777888999",
            "nombres": "Marta",
            "apellidos": "Díaz",
            "celular": "300123456789",
            "fecha_nacimiento": "1990-01-01",
        }
        res_largo = self.client.post("/api/usuarios/registro/", payload_largo)
        assert res_largo.status_code == status.HTTP_400_BAD_REQUEST

    def test_rechazar_celular_duplicado(self):
        """QA: Debe rechazar el registro si el celular ya pertenece a otra cuenta."""
        payload = {
            "email": "duplicado@domipedidos.com",
            "password": "Password123!",
            "tipo_documento": "CC",
            "num_documento": "555444333",
            "nombres": "Lucía",
            "apellidos": "Torres",
            "celular": "3001234567",  # Ya asignado a cliente_existente
            "fecha_nacimiento": "1997-11-12",
        }
        response = self.client.post("/api/usuarios/registro/", payload)
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "celular" in response.data