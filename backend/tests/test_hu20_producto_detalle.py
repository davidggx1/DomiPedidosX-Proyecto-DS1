import pytest
from rest_framework import status
from rest_framework.test import APIClient
from menu.models import (
    CategoriaMenu,
    Insumo,
    Producto,
    ProductoInsumo,
)


@pytest.mark.django_db
class TestHU20DetalleProducto:

    @pytest.fixture(autouse=True)
    def setup(self):
        self.client = APIClient()

        self.categoria = CategoriaMenu.objects.create(nombre="Hamburguesas")

        # Producto Disponible (activo=True)
        self.producto_disponible = Producto.objects.create(
            categoria=self.categoria,
            nombre="Hamburguesa Especial",
            descripcion="Carne 100% res con tocino y queso",
            precio_base=22000.00,
            tiempo_preparacion=15,
            activo=True,
        )

        # Producto No Disponible (activo=False)
        self.producto_no_disponible = Producto.objects.create(
            categoria=self.categoria,
            nombre="Malteada de Mora",
            descripcion="Malteada artesanal",
            precio_base=10000.00,
            tiempo_preparacion=5,
            activo=False,
        )

        # Insumos / Ingredientes
        self.insumo_cebolla = Insumo.objects.create(
            nombre="Cebolla caramelizada", unidad_medida="g"
        )
        self.insumo_carne = Insumo.objects.create(
            nombre="Carne de res 150g", unidad_medida="unidad"
        )

        # Ingrediente excluible (removible por cliente)
        ProductoInsumo.objects.create(
            producto=self.producto_disponible,
            insumo=self.insumo_cebolla,
            cantidad_necesaria=30,
            es_excluible=True,
        )
        # Ingrediente obligatorio
        ProductoInsumo.objects.create(
            producto=self.producto_disponible,
            insumo=self.insumo_carne,
            cantidad_necesaria=1,
            es_excluible=False,
        )

    def test_obtener_detalle_producto_disponible(self):
        """QA: Debe responder 200 OK con ingrediente removible u obligatorio diferenciados."""
        url = f"/api/menu/productos/{self.producto_disponible.id}/"
        response = self.client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data["nombre"] == "Hamburguesa Especial"
        assert response.data["disponible"] is True
        assert len(response.data["ingredientes"]) == 2

        excluibles = [ing for ing in response.data["ingredientes"] if ing["es_excluible"]]
        obligatorios = [ing for ing in response.data["ingredientes"] if not ing["es_excluible"]]

        assert len(excluibles) == 1
        assert excluibles[0]["nombre"] == "Cebolla caramelizada"
        assert len(obligatorios) == 1
        assert obligatorios[0]["nombre"] == "Carne de res 150g"

    def test_obtener_detalle_producto_no_disponible(self):
        """QA: El detalle de un producto inactivo debe indicar disponible=False."""
        url = f"/api/menu/productos/{self.producto_no_disponible.id}/"
        response = self.client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data["nombre"] == "Malteada de Mora"
        assert response.data["disponible"] is False