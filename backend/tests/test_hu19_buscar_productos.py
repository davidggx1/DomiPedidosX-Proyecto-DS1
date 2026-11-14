import pytest
from rest_framework import status
from rest_framework.test import APIClient

from menu.models import CategoriaMenu, Producto
from sedes.models import Ciudad, Sede


@pytest.mark.django_db
class TestHU19BuscarProductosMenu:

    @pytest.fixture(autouse=True)
    def setup(self):
        self.client = APIClient()

        ciudad = Ciudad.objects.create(nombre="Palmira")
        self.sede = Sede.objects.create(
            ciudad=ciudad,
            nombre="Sede Principal",
            direccion="Calle 30 # 25-10",
            activa=True,
            latitud=3.53,
            longitud=-76.30,
            barrio="Centro",
            telefono="3001234567",
            correo="palmira@test.com",
        )

        self.cat_bebidas = CategoriaMenu.objects.create(nombre="Bebidas", activa=True)
        self.cat_fuertes = CategoriaMenu.objects.create(nombre="Platos Fuertes", activa=True)

        self.prod_jugo = Producto.objects.create(
            categoria=self.cat_bebidas,
            nombre="Jugo de Maracuyá",
            precio_base=7000,
            tiempo_preparacion=5,
            activo=True,
        )
        self.prod_limonada = Producto.objects.create(
            categoria=self.cat_bebidas,
            nombre="Limonada de Coco",
            precio_base=8500,
            tiempo_preparacion=5,
            activo=True,
        )
        self.prod_patacon = Producto.objects.create(
            categoria=self.cat_fuertes,
            nombre="Patacón con Carne",
            precio_base=18000,
            tiempo_preparacion=15,
            activo=True,
        )

    def _nombres_en_respuesta(self, data):
        return [
            prod["nombre"]
            for cat in data["categorias"]
            for prod in cat["productos"]
        ]

    def test_criterio1_busqueda_insensible_mayusculas_y_tildes(self):
        """Busca 'maracuya' sin tilde y en minúsculas y encuentra 'Jugo de Maracuyá'."""
        url = f"/api/menu/sedes/{self.sede.id}/menu/"
        response = self.client.get(url, {"q": "maracuya"})

        assert response.status_code == status.HTTP_200_OK
        nombres = self._nombres_en_respuesta(response.data)
        assert nombres == ["Jugo de Maracuyá"]

    def test_criterio2_combina_con_filtro_categoria(self):
        """Combina búsqueda con ?categoria=<id> devolviendo solo coincidencias de esa categoría."""
        url = f"/api/menu/sedes/{self.sede.id}/menu/"
        # Buscar 'co' (presente en 'Limonada de Coco' y 'Patacón con Carne') filtrado por Bebidas
        response = self.client.get(url, {"q": "co", "categoria": self.cat_bebidas.id})

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data["categorias"]) == 1
        assert response.data["categorias"][0]["id"] == self.cat_bebidas.id
        nombres = self._nombres_en_respuesta(response.data)
        assert nombres == ["Limonada de Coco"]

    def test_criterio3_limpiar_busqueda_restaura_catalogo_completo(self):
        """Sin parámetro q (o vacío), retorna todos los productos activos del catálogo."""
        url = f"/api/menu/sedes/{self.sede.id}/menu/"
        response = self.client.get(url, {"q": ""})

        assert response.status_code == status.HTTP_200_OK
        nombres = self._nombres_en_respuesta(response.data)
        assert set(nombres) == {"Jugo de Maracuyá", "Limonada de Coco", "Patacón con Carne"}