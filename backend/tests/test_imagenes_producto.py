import io

import pytest
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image
from rest_framework import status
from rest_framework.test import APIClient

from menu import serializers as menu_serializers
from menu.models import CategoriaMenu, Producto

User = get_user_model()


def crear_archivo(formato="PNG", nombre="foto.png", tipo="image/png"):
    """Generates a real image in memory to upload it in the tests"""
    buffer = io.BytesIO()
    Image.new("RGB", (40, 40), color=(200, 30, 30)).save(buffer, format=formato)
    return SimpleUploadedFile(nombre, buffer.getvalue(), content_type=tipo)


@pytest.mark.django_db
class TestImagenProducto:

    @pytest.fixture(autouse=True)
    def setup(self, settings, tmp_path):
        # Test images go to a temp folder, not to the project
        settings.MEDIA_ROOT = tmp_path
        self.client = APIClient()
        self.admin = User.objects.create_user(
            username="admin", email="admin@domipedidos.com",
            password="Password123!", is_staff=True,
        )
        self.cliente = User.objects.create_user(
            username="cliente", email="cliente@domipedidos.com",
            password="Password123!",
        )
        categoria = CategoriaMenu.objects.create(nombre="Hamburguesas")
        self.producto = Producto.objects.create(
            categoria=categoria, nombre="Clásica",
            precio_base=15000, tiempo_preparacion=10,
        )
        self.url = f"/api/menu/productos/{self.producto.id}/imagen/"

    def test_admin_sube_imagen_valida(self):
        self.client.force_authenticate(user=self.admin)
        respuesta = self.client.post(self.url, {"imagen": crear_archivo()}, format="multipart")
        assert respuesta.status_code == status.HTTP_200_OK
        self.producto.refresh_from_db()
        assert self.producto.imagen.name.startswith("productos/")
        assert self.producto.imagen.storage.exists(self.producto.imagen.name)
        assert respuesta.data["imagen"].endswith(self.producto.imagen.name)

    def test_acepta_jpg_y_webp(self):
        self.client.force_authenticate(user=self.admin)
        for formato, nombre, tipo in [("JPEG", "a.jpg", "image/jpeg"), ("WEBP", "a.webp", "image/webp")]:
            archivo = crear_archivo(formato, nombre, tipo)
            respuesta = self.client.post(self.url, {"imagen": archivo}, format="multipart")
            assert respuesta.status_code == status.HTTP_200_OK

    def test_cliente_no_puede_subir(self):
        self.client.force_authenticate(user=self.cliente)
        respuesta = self.client.post(self.url, {"imagen": crear_archivo()}, format="multipart")
        assert respuesta.status_code == status.HTTP_403_FORBIDDEN

    def test_sin_autenticar_recibe_401(self):
        respuesta = self.client.post(self.url, {"imagen": crear_archivo()}, format="multipart")
        assert respuesta.status_code == status.HTTP_401_UNAUTHORIZED

    def test_rechaza_archivo_que_no_es_imagen(self):
        self.client.force_authenticate(user=self.admin)
        falso = SimpleUploadedFile("virus.png", b"esto no es una imagen", content_type="image/png")
        respuesta = self.client.post(self.url, {"imagen": falso}, format="multipart")
        assert respuesta.status_code == status.HTTP_400_BAD_REQUEST

    def test_rechaza_formato_no_permitido(self):
        self.client.force_authenticate(user=self.admin)
        gif = crear_archivo("GIF", "anim.gif", "image/gif")
        respuesta = self.client.post(self.url, {"imagen": gif}, format="multipart")
        assert respuesta.status_code == status.HTTP_400_BAD_REQUEST
        assert "Formato no permitido" in str(respuesta.data["imagen"])

    def test_rechaza_imagen_demasiado_grande(self, monkeypatch):
        monkeypatch.setattr(menu_serializers, "TAMANO_MAX_BYTES", 100)
        self.client.force_authenticate(user=self.admin)
        respuesta = self.client.post(self.url, {"imagen": crear_archivo()}, format="multipart")
        assert respuesta.status_code == status.HTTP_400_BAD_REQUEST
        assert "no puede superar" in str(respuesta.data["imagen"])

    def test_reemplazar_borra_el_archivo_anterior(self):
        self.client.force_authenticate(user=self.admin)
        self.client.post(self.url, {"imagen": crear_archivo()}, format="multipart")
        self.producto.refresh_from_db()
        primera = self.producto.imagen.name

        self.client.post(self.url, {"imagen": crear_archivo()}, format="multipart")
        self.producto.refresh_from_db()
        assert self.producto.imagen.name != primera
        assert not self.producto.imagen.storage.exists(primera)

    def test_eliminar_imagen(self):
        self.client.force_authenticate(user=self.admin)
        self.client.post(self.url, {"imagen": crear_archivo()}, format="multipart")
        self.producto.refresh_from_db()
        nombre = self.producto.imagen.name

        respuesta = self.client.delete(self.url)
        assert respuesta.status_code == status.HTTP_204_NO_CONTENT
        self.producto.refresh_from_db()
        assert not self.producto.imagen
        assert not self.producto.imagen.storage.exists(nombre)

    def test_producto_inexistente_devuelve_404(self):
        self.client.force_authenticate(user=self.admin)
        respuesta = self.client.post(
            "/api/menu/productos/99999/imagen/", {"imagen": crear_archivo()}, format="multipart"
        )
        assert respuesta.status_code == status.HTTP_404_NOT_FOUND
