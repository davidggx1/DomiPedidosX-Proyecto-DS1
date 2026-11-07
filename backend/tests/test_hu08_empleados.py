import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from rest_framework import status
from rest_framework.test import APIClient

from sedes.models import Ciudad, Sede

User = get_user_model()


@pytest.mark.django_db
class TestHU08RegistroPersonal:

    @pytest.fixture(autouse=True)
    def setup(self):
        self.client = APIClient()

        # Crear Ciudad y Sede de prueba
        self.ciudad = Ciudad.objects.create(nombre="Cali")
        self.sede = Sede.objects.create(
            ciudad=self.ciudad,
            nombre="Sede San Fernando",
            direccion="Calle 5 # 36-00",
            barrio="San Fernando",
            latitud=3.43,
            longitud=-76.52,
            telefono="3000000000",
            correo="sanfernando@domipedidos.com",
        )

        # Crear Administrador (usando grupo en minúsculas 'administrador' según roles.py)
        self.admin_user = User.objects.create_user(
            username="admin@domipedidos.com",
            email="admin@domipedidos.com",
            password="AdminPassword123!",
            is_staff=True,
        )
        admin_group, _ = Group.objects.get_or_create(name="administrador")
        self.admin_user.groups.add(admin_group)

        # Crear Usuario Cliente (No Admin)
        self.cliente_user = User.objects.create_user(
            username="cliente@domipedidos.com",
            email="cliente@domipedidos.com",
            password="ClientPassword123!",
            is_staff=False,
        )

    def test_crear_operador_exitoso_como_admin(self):
        """Un administrador crea exitosamente un Operador con sede asignada y verifica asignación de grupo en minúsculas."""
        self.client.force_authenticate(user=self.admin_user)
        payload = {
            "email": "operador1@domipedidos.com",
            "nombres": "Juan",
            "apellidos": "Pérez",
            "tipo_documento": "CC",
            "num_documento": "1098765432",
            "celular": "3151234567",
            "direccion": "Carrera 1 # 2-3",
            "rol": "OPERADOR",
            "sede_id": self.sede.id,
        }
        response = self.client.post("/api/usuarios/empleados/", payload)
        assert response.status_code == status.HTTP_201_CREATED
        assert "contrasena_inicial" in response.data

        # Verificar que se asignó el grupo en minúsculas 'operador'
        usuario_creado = User.objects.get(email="operador1@domipedidos.com")
        assert usuario_creado.groups.filter(name="operador").exists()

    def test_empleado_registrado_puede_hacer_login_personal(self):
        """Un empleado recién creado con rol 'OPERADOR' puede iniciar sesión en /login-personal/."""
        self.client.force_authenticate(user=self.admin_user)
        payload = {
            "email": "operador.login@domipedidos.com",
            "password": "PasswordSegura123!",
            "nombres": "Carlos",
            "apellidos": "Gómez",
            "tipo_documento": "CC",
            "num_documento": "1098765999",
            "celular": "3151239999",
            "direccion": "Carrera 1 # 2-3",
            "rol": "OPERADOR",
            "sede_id": self.sede.id,
        }
        res_crear = self.client.post("/api/usuarios/empleados/", payload)
        assert res_crear.status_code == status.HTTP_201_CREATED

        # Intentar Login Personal desautenticando el admin
        self.client.force_authenticate(user=None)
        res_login = self.client.post(
            "/api/usuarios/login-personal/",
            {"email": "operador.login@domipedidos.com", "password": "PasswordSegura123!"},
            format="json",
        )
        assert res_login.status_code == status.HTTP_200_OK
        assert "access" in res_login.data

    def test_admin_no_requiere_sede(self):
        """Un Administrador puede ser registrado sin especificar una sede."""
        self.client.force_authenticate(user=self.admin_user)
        payload = {
            "email": "admin2@domipedidos.com",
            "nombres": "María",
            "apellidos": "Gómez",
            "tipo_documento": "CC",
            "num_documento": "1011223344",
            "celular": "3109876543",
            "direccion": "Calle 10 # 20-30",
            "rol": "ADMINISTRADOR",
            "sede_id": None,
        }
        response = self.client.post("/api/usuarios/empleados/", payload, format="json")
        assert response.status_code == status.HTTP_201_CREATED

    def test_qa_rechazar_falta_de_sede_en_rol_operativo(self):
        """QA: Rechazar registro de Operador/Cocina/Repartidor si falta la sede obligatoria."""
        self.client.force_authenticate(user=self.admin_user)
        payload = {
            "email": "cocina1@domipedidos.com",
            "nombres": "Pedro",
            "apellidos": "Ramírez",
            "tipo_documento": "CC",
            "num_documento": "1231231234",
            "celular": "3201234567",
            "direccion": "Calle 15 # 4-5",
            "rol": "COCINA",
            "sede_id": None,  # Error: obligatorio para COCINA
        }
        response = self.client.post("/api/usuarios/empleados/", payload, format="json")
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "sede_id" in response.data

    def test_qa_rechazar_correo_duplicado(self):
        """QA: Rechazar el registro si el correo ya pertenece a otra cuenta."""
        self.client.force_authenticate(user=self.admin_user)
        payload = {
            "email": "cliente@domipedidos.com",  # Ya existe
            "nombres": "Laura",
            "apellidos": "Torres",
            "tipo_documento": "CC",
            "num_documento": "9998887776",
            "celular": "3009998877",
            "direccion": "Av 6 # 10-12",
            "rol": "OPERADOR",
            "sede_id": self.sede.id,
        }
        response = self.client.post("/api/usuarios/empleados/", payload)
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "email" in response.data

    def test_qa_denegar_acceso_a_no_administrador(self):
        """QA: Un usuario sin rol administrador (Cliente/Operador) recibe HTTP 403."""
        self.client.force_authenticate(user=self.cliente_user)
        payload = {
            "email": "hacker@domipedidos.com",
            "nombres": "Test",
            "apellidos": "User",
            "tipo_documento": "CC",
            "num_documento": "1111111111",
            "celular": "3000000001",
            "direccion": "Calle Falsa 123",
            "rol": "OPERADOR",
            "sede_id": self.sede.id,
        }
        response = self.client.post("/api/usuarios/empleados/", payload)
        assert response.status_code == status.HTTP_403_FORBIDDEN