"""HU-79: delete products (soft delete)."""
import pytest
from django.contrib.auth.models import Group
from rest_framework.test import APIClient

from inventario.models import AlertaInventario, InventarioProducto
from menu.models import CategoriaMenu, Producto
from pedidos.models import DetallePedido, Pedido
from sedes.models import Ciudad, Sede
from usuarios.models import Usuario

URL = "/api/menu/productos/"

pytestmark = pytest.mark.django_db


def _usuario(correo, grupo=None):
    usuario = Usuario.objects.create_user(username=correo, email=correo, password="ClaveSegura2026")
    if grupo:
        usuario.groups.add(Group.objects.get_or_create(name=grupo)[0])
    return usuario


def _api(usuario=None):
    api = APIClient()
    if usuario:
        api.force_authenticate(user=usuario)
    return api


def _menu_cliente(sede):
    """Products the client sees in the menu of the sede (public endpoint)."""
    respuesta = APIClient().get(f"/api/menu/sedes/{sede.id}/menu/")
    assert respuesta.status_code == 200
    return {p["id"]: p for c in respuesta.data["categorias"] for p in c["productos"]}


def _validar(sede, ids):
    respuesta = APIClient().post(
        f"/api/menu/sedes/{sede.id}/validar-carrito/", {"productos": ids}, format="json"
    )
    assert respuesta.status_code == 200
    return respuesta.data


@pytest.fixture
def operador():
    return _api(_usuario("operador@correo.com", "operador"))


@pytest.fixture
def categoria():
    return CategoriaMenu.objects.create(nombre="Hamburguesas")


@pytest.fixture
def sede():
    ciudad, _ = Ciudad.objects.get_or_create(nombre="Cali")
    return Sede.objects.create(
        ciudad=ciudad, nombre="Sede Centro", direccion="Cra 1 # 2-3", latitud=3.45,
        longitud=-76.53, barrio="Centro", telefono="3000000000", correo="centro@domi.com",
    )


@pytest.fixture
def producto(categoria, sede):
    producto = Producto.objects.create(
        categoria=categoria, nombre="Clásica", precio_base=15000, tiempo_preparacion=10,
        tipo_control_stock=Producto.TipoControlStock.PRODUCTO,
    )
    InventarioProducto.objects.create(
        sede=sede, producto=producto, stock_actual=20, stock_minimo=5, disponible=True
    )
    return producto


# --- Criterio 1: borrado lógico, oculto al cliente y conservado en pedidos viejos ------

def test_eliminar_deja_el_producto_inactivo_sin_borrar_el_registro(operador, producto):
    respuesta = operador.delete(f"{URL}{producto.id}/")

    assert respuesta.status_code == 204
    producto.refresh_from_db()
    assert producto.activo is False
    assert Producto.objects.filter(pk=producto.pk).exists()


def test_el_cliente_ya_no_lo_ve_en_el_menu(operador, producto, sede):
    assert producto.id in _menu_cliente(sede)

    operador.delete(f"{URL}{producto.id}/")

    assert producto.id not in _menu_cliente(sede)


def test_el_detalle_publico_de_un_producto_eliminado_da_404(operador, producto):
    assert APIClient().get(f"{URL}{producto.id}/").status_code == 200

    operador.delete(f"{URL}{producto.id}/")

    assert APIClient().get(f"{URL}{producto.id}/").status_code == 404


def test_los_pedidos_viejos_conservan_el_producto(operador, producto, sede):
    pedido = Pedido.objects.create(sede=sede, numero_pedido="P-HU79")
    detalle = DetallePedido.objects.create(
        pedido=pedido, producto=producto, cantidad=2,
        precio_unitario=producto.precio_base, subtotal=producto.precio_base * 2,
    )

    assert operador.delete(f"{URL}{producto.id}/").status_code == 204

    detalle.refresh_from_db()
    assert detalle.producto == producto
    assert detalle.producto.nombre == "Clásica"
    assert detalle.subtotal == 30000
    assert Pedido.objects.filter(pk=pedido.pk).exists()


def test_el_operador_lo_sigue_viendo_como_inactivo_y_lo_puede_restaurar(operador, producto, sede):
    operador.delete(f"{URL}{producto.id}/")

    inactivos = operador.get(URL, {"activo": "false"}).data
    assert producto.id in [p["id"] for p in inactivos]

    assert operador.patch(f"{URL}{producto.id}/", {"activo": True}, format="json").status_code == 200
    assert producto.id in _menu_cliente(sede)


def test_eliminar_dos_veces_es_inofensivo(operador, producto):
    assert operador.delete(f"{URL}{producto.id}/").status_code == 204
    assert operador.delete(f"{URL}{producto.id}/").status_code == 204
    assert operador.delete(f"{URL}99999/").status_code == 404


# --- Limpieza de carritos: el cliente sabe qué productos fueron retirados -------------

def test_validar_carrito_marca_los_productos_retirados(operador, producto, sede):
    assert _validar(sede, [producto.id])["retirados"] == []

    operador.delete(f"{URL}{producto.id}/")

    datos = _validar(sede, [producto.id])
    assert datos["retirados"] == [producto.id]
    assert datos["valido"] is False
    assert datos["no_disponibles"] == [{"id": producto.id, "nombre": "Clásica"}]


def test_un_producto_agotado_en_la_sede_no_cuenta_como_retirado(operador, producto, sede, categoria):
    agotado = Producto.objects.create(
        categoria=categoria, nombre="Doble", precio_base=20000, tiempo_preparacion=10,
    )
    InventarioProducto.objects.create(sede=sede, producto=agotado, disponible=False)

    datos = _validar(sede, [producto.id, agotado.id])

    assert [p["id"] for p in datos["no_disponibles"]] == [agotado.id]
    assert datos["retirados"] == []


def test_un_id_que_ya_no_existe_cuenta_como_retirado(sede):
    assert _validar(sede, [99999])["retirados"] == [99999]


# --- Alertas de stock bajo (HU-16): un producto eliminado ya no alerta ----------------

def test_eliminar_un_producto_cierra_su_alerta_de_stock_bajo(operador, producto):
    inventario = InventarioProducto.objects.get(producto=producto)
    inventario.stock_actual = 2
    inventario.save()
    assert AlertaInventario.objects.filter(estado="activa").count() == 1

    operador.delete(f"{URL}{producto.id}/")

    assert AlertaInventario.objects.filter(estado="activa").count() == 0
    assert AlertaInventario.objects.filter(estado="resuelta").count() == 1


def test_un_producto_eliminado_no_genera_alertas_nuevas(operador, producto):
    operador.delete(f"{URL}{producto.id}/")
    inventario = InventarioProducto.objects.get(producto=producto)

    inventario.stock_actual = 1
    inventario.save()

    assert not AlertaInventario.objects.filter(estado="activa").exists()


def test_restaurar_un_producto_con_stock_bajo_vuelve_a_alertar(operador, producto):
    inventario = InventarioProducto.objects.get(producto=producto)
    inventario.stock_actual = 2
    inventario.save()
    operador.delete(f"{URL}{producto.id}/")
    assert not AlertaInventario.objects.filter(estado="activa").exists()

    operador.patch(f"{URL}{producto.id}/", {"activo": True}, format="json")

    assert AlertaInventario.objects.filter(estado="activa").count() == 1


# --- Permisos --------------------------------------------------------------------------

def test_sin_sesion_recibe_401(producto):
    assert _api().delete(f"{URL}{producto.id}/").status_code == 401
    producto.refresh_from_db()
    assert producto.activo is True


@pytest.mark.parametrize("grupo", [None, "cliente", "cocina", "repartidor"])
def test_otros_roles_reciben_403(producto, grupo):
    api = _api(_usuario("otro@correo.com", grupo))

    assert api.delete(f"{URL}{producto.id}/").status_code == 403
    producto.refresh_from_db()
    assert producto.activo is True


def test_el_administrador_tambien_puede_eliminar(producto):
    api = _api(_usuario("admin@correo.com", "administrador"))

    assert api.delete(f"{URL}{producto.id}/").status_code == 204
