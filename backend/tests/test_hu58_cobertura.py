import pytest
from rest_framework import status
from rest_framework.test import APIClient
from django.contrib.auth import get_user_model
from sedes.models import Ciudad, Sede, ZonaCobertura

User = get_user_model()


@pytest.mark.django_db
class TestHU58ValidacionCobertura:

    @pytest.fixture(autouse=True)
    def setup(self):
        self.client = APIClient()
        self.ciudad = Ciudad.objects.create(nombre="Cali")

        # Sede 1: San Fernando (Centro Lat 3.450, Lng -76.530)
        self.sede_san_fernando = Sede.objects.create(
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
        self.zona_san_fernando = ZonaCobertura.objects.create(
            sede=self.sede_san_fernando,
            nombre="Zona San Fernando 3KM",
            radio=3.0,
            centro_latitud=3.450,
            centro_longitud=-76.530,
            tarifa_domicilio=3000.00,
            tiempo_estimado=25,
            pedido_minimo=15000.00,
            activo=True
        )

        # Sede 2: Norte (Granada - Lat 3.465, Lng -76.528) - Solapada en ciertas zonas
        self.sede_norte = Sede.objects.create(
            ciudad=self.ciudad,
            nombre="Sede Norte",
            direccion="Avenida 6N # 12-30",
            activa=True,
            latitud=3.465,
            longitud=-76.528,
            barrio="Granada",
            telefono="3109876543",
            correo="norte@domipedidos.com"
        )
        self.zona_norte = ZonaCobertura.objects.create(
            sede=self.sede_norte,
            nombre="Zona Norte 4KM",
            radio=4.0,
            centro_latitud=3.465,
            centro_longitud=-76.528,
            tarifa_domicilio=3500.00,
            tiempo_estimado=30,
            pedido_minimo=15000.00,
            activo=True
        )

    def test_criterio1_direccion_con_cobertura_exitosa(self):
        """1. Dirección dentro del radio confirma cobertura y asigna sede."""
        # Punto a 1km de San Fernando
        payload = {"latitud": 3.452, "longitud": -76.531}
        response = self.client.post('/api/sedes/validar-cobertura/', payload)

        assert response.status_code == status.HTTP_200_OK
        assert response.data["cubierto"] is True
        assert response.data["sede"]["id"] == self.sede_san_fernando.id

    def test_criterio2_direccion_fuera_de_cobertura_bloquea(self):
        """2. Dirección fuera de todas las áreas notifica al cliente."""
        # Punto lejano (a 20km)
        payload = {"latitud": 3.600, "longitud": -76.700}
        response = self.client.post('/api/sedes/validar-cobertura/', payload)

        assert response.status_code == status.HTTP_200_OK
        assert response.data["cubierto"] is False
        assert "fuera de nuestra zona" in response.data["mensaje"]

    def test_criterio3_interseccion_asigna_sede_mas_cercana(self):
        """3. En intersecciones asigna la sede geográficamente más cercana."""
        # Punto intermedio (Lat 3.460, Lng -76.529) cubierto por ambas
        payload = {"latitud": 3.460, "longitud": -76.529}
        response = self.client.post('/api/sedes/validar-cobertura/', payload)

        assert response.status_code == status.HTTP_200_OK
        assert response.data["cubierto"] is True
        # Debe asignar a Sede Norte por ser más cercana al punto (dist ~0.55km vs ~1.1km)
        assert response.data["sede"]["id"] == self.sede_norte.id