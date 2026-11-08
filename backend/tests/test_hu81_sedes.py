import pytest
from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APIClient
from sedes.models import Ciudad, Sede

User = get_user_model()


@pytest.mark.django_db
class TestHU81SedesBackend:

    @pytest.fixture(autouse=True)
    def setup(self):
        self.client = APIClient()

        # 1. Datos iniciales
        self.ciudad = Ciudad.objects.create(nombre="Cali")

        # 2. Creación de usuarios para pruebas de permisos (Admin vs Cliente)
        self.admin_user = User.objects.create_user(
            username="admin_user",
            email="admin@domipedidos.com",
            password="Password123!",
            is_staff=True
        )
        if hasattr(self.admin_user, 'rol'):
            self.admin_user.rol = 'ADMINISTRADOR'
            self.admin_user.save()

        self.cliente_user = User.objects.create_user(
            username="cliente_user",
            email="cliente@domipedidos.com",
            password="Password123!",
            is_staff=False
        )
        if hasattr(self.cliente_user, 'rol'):
            self.cliente_user.rol = 'CLIENTE'
            self.cliente_user.save()

        # 3. Sede inicial de prueba
        self.sede_existente = Sede.objects.create(
            ciudad=self.ciudad,
            nombre="Sede San Fernando",
            direccion="Calle 5 # 24-00",
            activa=True,
            latitud=3.451,
            longitud=-76.532,
            barrio="San Fernando",
            telefono="3001234567",
            correo="sanfernando@domipedidos.com"
        )

    # --- PRUEBA 1: Registro Exitoso por Administrador ---
    def test_crear_sede_exitoso_como_admin(self):
        """Un administrador puede registrar una nueva sede válida."""
        self.client.force_authenticate(user=self.admin_user)
        payload = {
            "ciudad": self.ciudad.id,
            "nombre": "Sede Norte",
            "direccion": "Avenida 6N # 12-30",
            "activa": True,
            "latitud": 3.465,
            "longitud": -76.528,
            "barrio": "Granada",
            "telefono": "3109876543",
            "correo": "norte@domipedidos.com"
        }
        response = self.client.post('/api/sedes/', payload)
        assert response.status_code == status.HTTP_201_CREATED
        assert Sede.objects.filter(nombre="Sede Norte").exists()

    # --- PRUEBA 2: QA Validar Nombre Duplicado ---
    def test_rechazar_nombre_duplicado(self):
        """QA: Debe rechazar el registro si el nombre ya existe."""
        self.client.force_authenticate(user=self.admin_user)
        payload = {
            "ciudad": self.ciudad.id,
            "nombre": "sede san fernando",  # Mismo nombre en minúsculas
            "direccion": "Otra dirección # 12-34",
            "activa": True,
            "latitud": 3.400,
            "longitud": -76.500,
            "barrio": "Centro",
            "telefono": "3000000000",
            "correo": "otro@domipedidos.com"
        }
        response = self.client.post('/api/sedes/', payload)
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "nombre" in response.data
        assert "Ya existe una sede registrada con este nombre." in str(response.data["nombre"])

    # --- PRUEBA 3: QA Validar Campos Obligatorios ---
    def test_validar_campos_obligatorios(self):
        """QA: Debe rechazar el formulario si faltan campos requeridos."""
        self.client.force_authenticate(user=self.admin_user)
        payload = {
            "nombre": "",        # Vacío
            "direccion": "",     # Vacío
            "telefono": "",      # Vacío
            "correo": "invalido" # Correo con mal formato
        }
        response = self.client.post('/api/sedes/', payload)
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "nombre" in response.data
        assert "direccion" in response.data
        assert "ciudad" in response.data

    # --- PRUEBA 4: Control de Acceso (Solo Administrador) ---
    def test_denegar_crud_a_usuario_no_admin(self):
        """QA: Usuarios sin rol de Admin no pueden crear ni editar sedes."""
        self.client.force_authenticate(user=self.cliente_user)
        payload = {
            "ciudad": self.ciudad.id,
            "nombre": "Sede No Autorizada",
            "direccion": "Calle 1",
            "latitud": 3.4,
            "longitud": -76.5,
            "barrio": "Sur",
            "telefono": "3000000000",
            "correo": "test@test.com"
        }
        # Intento de creación
        response = self.client.post('/api/sedes/', payload)
        assert response.status_code == status.HTTP_403_FORBIDDEN

        # Intento de modificación
        response = self.client.patch(f'/api/sedes/{self.sede_existente.id}/', {"activa": False})
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_ocultar_sedes_inactivas_en_catalogo_cliente(self):
        """QA: El filtro ?activa=true oculta las sedes inactivas del público."""
        sede_inactiva = Sede.objects.create(
            ciudad=self.ciudad,
            nombre="Sede Inactiva Sur",
            direccion="Carrera 100 # 15-00",
            activa=False,
            latitud=3.350,
            longitud=-76.520,
            barrio="Ciudad Jardín",
            telefono="3001112233",
            correo="inactiva@domipedidos.com"
        )

        response = self.client.get('/api/sedes/?activa=true')
        assert response.status_code == status.HTTP_200_OK

        # Extraer la lista sin importar si la API retorna lista directa o dict con "results" (paginación)
        data = response.data.get('results', response.data) if isinstance(response.data, dict) else response.data
        ids_retornados = [sede["id"] for sede in data]

        assert self.sede_existente.id in ids_retornados
        assert sede_inactiva.id not in ids_retornados

    # --- PRUEBA 6: Cambio de Estado (Desactivación) ---
    def test_desactivar_sede_exitoso(self):
        """Un admin puede cambiar el estado de activa a False."""
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.patch(
            f'/api/sedes/{self.sede_existente.id}/',
            {"activa": False},
            format='json'
        )
        assert response.status_code == status.HTTP_200_OK
        self.sede_existente.refresh_from_db()
        assert self.sede_existente.activa is False