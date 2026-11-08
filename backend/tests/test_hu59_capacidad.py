import pytest
from rest_framework import status
from rest_framework.test import APIClient
from django.contrib.auth import get_user_model
from sedes.models import Ciudad, Sede, CapacidadSede
from pedidos.models import Pedido, EstadoPedido

User = get_user_model()

@pytest.mark.django_db
class TestHU59CapacidadSede:

    @pytest.fixture(autouse=True)
    def setup(self):
        self.client = APIClient()
        self.ciudad = Ciudad.objects.create(nombre="Cali")
        self.sede = Sede.objects.create(
            ciudad=self.ciudad,
            nombre="Sede San Fernando",
            direccion="Calle 5 # 24-00",
            activa=True,
            latitud=3.450,
            longitud=-76.530,
            barrio="San Fernando",
            telefono="3001234567",
            correo="sanfernando@domipedidos.com"
        )
        self.admin_user = User.objects.create_user(
            username="admin_capacidad",
            email="admin@domipedidos.com",
            password="Password123!",
            is_staff=True
        )
        if hasattr(self.admin_user, 'rol'):
            self.admin_user.rol = 'ADMINISTRADOR'
            self.admin_user.save()

    def test_criterio2_rechazar_capacidad_menor_a_uno(self):
        """Rechazar capacidades < 1."""
        self.client.force_authenticate(user=self.admin_user)
        payload = {
            "sede": self.sede.id,
            "hora_inicio": "11:00:00",
            "hora_fin": "15:00:00",
            "dias_semana": "lunes,martes",
            "max_pedidos_simultaneos": 0,  # Inválido
            "umbral_alerta": 0
        }
        response = self.client.post('/api/capacidades/', payload, format='json')
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "max_pedidos_simultaneos" in response.data

    def test_criterio2_bloquear_franjas_solapadas(self):
        """Bloquear franjas horarias que se solapen en los mismos días."""
        CapacidadSede.objects.create(
            sede=self.sede,
            hora_inicio="11:00:00",
            hora_fin="15:00:00",
            dias_semana="lunes,martes",
            max_pedidos_simultaneos=5,
            umbral_alerta=3
        )
        self.client.force_authenticate(user=self.admin_user)
        # Franja solapada (14:00 a 18:00 el día martes)
        payload = {
            "sede": self.sede.id,
            "hora_inicio": "14:00:00",
            "hora_fin": "18:00:00",
            "dias_semana": "martes,miercoles",
            "max_pedidos_simultaneos": 8,
            "umbral_alerta": 5
        }
        response = self.client.post('/api/capacidades/', payload, format='json')
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "non_field_errors" in response.data or "solapa" in str(response.data)