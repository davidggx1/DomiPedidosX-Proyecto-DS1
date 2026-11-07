"""Pruebas de los modelos: verifican que las restricciones de la base de datos funcionan."""
import pytest
from django.db import IntegrityError, transaction
from django.urls import reverse

from menu.models import CategoriaMenu, Producto
from pedidos.models import DetallePedido, Pedido
from promociones.models import Combo
from sedes.models import Ciudad, Sede
from usuarios.models import Cliente, DireccionEntrega, Usuario

pytestmark = pytest.mark.django_db

CLAVE = "ClaveSegura#2026"


@pytest.fixture
def sede():
    ciudad = Ciudad.objects.create(nombre="Cali")
    return Sede.objects.create(
        ciudad=ciudad, nombre="Sede Centro", direccion="Cra 1 # 2-3",
        latitud=3.45, longitud=-76.53, barrio="Centro",
        telefono="3000000000", correo="centro@domi.com",
    )


@pytest.fixture
def cliente():
    usuario = Usuario.objects.create_user(username="ana", email="ana@correo.com", password=CLAVE)
    return Cliente.objects.create(
        usuario=usuario, tipo_documento="CC", num_documento="123",
        nombres="Ana", apellidos="Pérez", celular="3001112222",
        fecha_nacimiento="2000-01-01",
    )


@pytest.fixture
def producto():
    categoria = CategoriaMenu.objects.create(nombre="Hamburguesas")
    return Producto.objects.create(
        categoria=categoria, nombre="Clásica", precio_base=15000, tiempo_preparacion=15,
    )


def test_usuario_inicia_sesion_con_correo():
    Usuario.objects.create_user(username="luis", email="luis@correo.com", password=CLAVE)
    assert Usuario.USERNAME_FIELD == "email"
    usuario = Usuario.objects.get(email="luis@correo.com")
    assert usuario.check_password(CLAVE)
    assert usuario.password != CLAVE  # la contraseña se guarda cifrada


def test_correo_de_usuario_es_unico():
    Usuario.objects.create_user(username="uno", email="repetido@correo.com", password=CLAVE)
    with pytest.raises(IntegrityError), transaction.atomic():
        Usuario.objects.create_user(username="dos", email="repetido@correo.com", password=CLAVE)


def test_solo_una_direccion_principal_por_cliente(cliente):
    ciudad = Ciudad.objects.create(nombre="Cali")
    datos = dict(ciudad=ciudad, cliente=cliente, latitud=3.4, longitud=-76.5, barrio="Centro")
    DireccionEntrega.objects.create(direccion="Calle 1", es_principal=True, **datos)
    DireccionEntrega.objects.create(direccion="Calle 2", es_principal=False, **datos)  # varias normales: OK
    with pytest.raises(IntegrityError), transaction.atomic():
        DireccionEntrega.objects.create(direccion="Calle 3", es_principal=True, **datos)


def test_detalle_pedido_exige_producto_o_combo_pero_no_ambos(sede, producto):
    pedido = Pedido.objects.create(sede=sede, numero_pedido="P-001")
    combo = Combo.objects.create(
        nombre="Combo", precio=20000, fecha_inicio="2026-01-01", fecha_vencimiento="2026-12-31",
    )
    base = dict(pedido=pedido, cantidad=1, precio_unitario=15000, subtotal=15000)

    DetallePedido.objects.create(producto=producto, **base)  # solo producto: OK
    DetallePedido.objects.create(combo=combo, **base)  # solo combo: OK
    with pytest.raises(IntegrityError), transaction.atomic():
        DetallePedido.objects.create(**base)  # ninguno
    with pytest.raises(IntegrityError), transaction.atomic():
        DetallePedido.objects.create(producto=producto, combo=combo, **base)  # ambos


def test_pedido_de_mostrador_no_requiere_cliente_ni_direccion(sede):
    pedido = Pedido.objects.create(sede=sede, numero_pedido="P-002", origen="mostrador")
    assert pedido.cliente is None and pedido.direccion_entrega is None
    assert pedido.estado == "recibido"


def test_panel_de_administracion_de_usuarios_carga(client):
    Usuario.objects.create_superuser(username="root", email="root@correo.com", password=CLAVE)
    client.force_login(Usuario.objects.get(email="root@correo.com"))
    assert client.get(reverse("admin:usuarios_usuario_changelist")).status_code == 200
    assert client.get(reverse("admin:usuarios_usuario_add")).status_code == 200
