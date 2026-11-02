"""Pruebas del comando seed_datos (SCRUM-22)."""
import pytest
from django.contrib.auth.models import Group
from django.core.management import call_command

from inventario.models import InventarioProducto
from menu.models import CategoriaMenu, Producto, ProductoInsumo
from sedes.models import Sede
from usuarios.models import Usuario

pytestmark = pytest.mark.django_db


def test_seed_crea_los_datos_basicos():
    call_command("seed_datos")

    admin = Usuario.objects.get(email="admin@domipedidosx.local")
    assert admin.is_superuser
    assert admin.groups.filter(name="administrador").exists()
    assert Group.objects.filter(name="operador").exists()
    assert Sede.objects.count() == 2
    assert CategoriaMenu.objects.filter(nombre="Postres").exists()
    assert Producto.objects.count() == 6
    assert ProductoInsumo.objects.filter(es_excluible=True).exists()


def test_seed_es_idempotente():
    call_command("seed_datos")
    call_command("seed_datos")

    assert Usuario.objects.filter(email="admin@domipedidosx.local").count() == 1
    assert Sede.objects.count() == 2
    assert Producto.objects.count() == 6


def test_producto_no_disponible_solo_en_una_sede():
    call_command("seed_datos")

    limonada = Producto.objects.get(nombre="Limonada natural")
    sur = InventarioProducto.objects.get(producto=limonada, sede__nombre="Sede Sur")
    centro = InventarioProducto.objects.get(producto=limonada, sede__nombre="Sede Centro")
    assert sur.disponible is False
    assert centro.disponible is True


def test_admin_puede_iniciar_sesion_con_la_clave_indicada():
    call_command("seed_datos", admin_password="OtraClave#2026")

    admin = Usuario.objects.get(email="admin@domipedidosx.local")
    assert admin.check_password("OtraClave#2026")
