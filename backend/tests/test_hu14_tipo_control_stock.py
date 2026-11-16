"""HU-11 / HU-14: choose the stock control type when creating and editing products."""
from datetime import date
from decimal import Decimal
from types import SimpleNamespace

import pytest
from django.contrib.auth.models import Group
from rest_framework.test import APIClient

from inventario.models import InventarioInsumo, InventarioProducto
from menu.models import CategoriaMenu, Insumo, Producto, ProductoInsumo
from pedidos.models import Pedido
from sedes.models import Ciudad, Sede, ZonaCobertura
from usuarios.models import Cliente, DireccionEntrega, Usuario

pytestmark = pytest.mark.django_db

URL = "/api/menu/productos/"
CONTROL = Producto.TipoControlStock
TIPOS = [CONTROL.PRODUCTO, CONTROL.INSUMOS, CONTROL.NINGUNO]


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


@pytest.fixture(autouse=True)
def media_temporal(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path


@pytest.fixture
def m():
    ciudad = Ciudad.objects.create(nombre="Cali")
    sede = Sede.objects.create(
        ciudad=ciudad, nombre="Centro", direccion="Cra 1 # 2-3", latitud=3.45, longitud=-76.53,
        barrio="Centro", telefono="3000000000", correo="centro@domi.com",
    )
    ZonaCobertura.objects.create(
        sede=sede, nombre="Zona", radio=5, centro_latitud=3.45, centro_longitud=-76.53,
        tarifa_domicilio=Decimal("3000"), tiempo_estimado=40, pedido_minimo=Decimal("0"),
    )
    usuario = _usuario("cli@correo.com")
    cliente = Cliente.objects.create(
        usuario=usuario, tipo_documento="CC", num_documento="1", nombres="Ana", apellidos="P",
        celular="3001234567", fecha_nacimiento=date(2000, 1, 1),
    )
    direccion = DireccionEntrega.objects.create(
        ciudad=ciudad, cliente=cliente, direccion="Calle 5", latitud=3.46, longitud=-76.53,
    )
    categoria = CategoriaMenu.objects.create(nombre="Platos")
    return SimpleNamespace(
        sede=sede, categoria=categoria, direccion=direccion, comprador=_api(usuario),
        operador=_api(_usuario("op@correo.com", "operador")),
    )


def _datos(m, **extra):
    return {
        "nombre": "Clásica", "precio_base": "15000", "tiempo_preparacion": 10,
        "categoria": m.categoria.pk, "sedes": [m.sede.pk], **extra,
    }


def _producto(m, control=CONTROL.NINGUNO, stock=0, nombre="Clásica"):
    producto = Producto.objects.create(
        categoria=m.categoria, nombre=nombre, precio_base=15000, tiempo_preparacion=10,
        tipo_control_stock=control,
    )
    InventarioProducto.objects.create(sede=m.sede, producto=producto, stock_actual=stock, disponible=True)
    return producto


def _receta(m, producto, stock, cantidad=2):
    insumo = Insumo.objects.create(nombre=f"Carne {producto.pk}", unidad_medida="unidad")
    ProductoInsumo.objects.create(producto=producto, insumo=insumo, cantidad_necesaria=cantidad)
    inventario = InventarioInsumo.objects.create(sede=m.sede, insumo=insumo, stock_actual=stock, disponible=True)
    return inventario


def _menu(m):
    respuesta = APIClient().get(f"/api/menu/sedes/{m.sede.pk}/menu/")
    assert respuesta.status_code == 200
    return {p["id"]: p for c in respuesta.data["categorias"] for p in c["productos"]}


def _validar(m, producto):
    respuesta = APIClient().post(
        f"/api/menu/sedes/{m.sede.pk}/validar-carrito/", {"productos": [producto.pk]}, format="json"
    )
    assert respuesta.status_code == 200
    return respuesta.data


def _comprar(m, producto, cantidad=1):
    return m.comprador.post(
        "/api/pedidos/confirmar/",
        {
            "sede_id": m.sede.pk, "direccion_id": m.direccion.pk, "metodo_pago": "tarjeta",
            "items": [{"producto_id": producto.pk, "cantidad": cantidad}],
        },
        format="json",
    )


# --- El operador elige el tipo al crear y al editar -------------------------------------

@pytest.mark.parametrize("tipo", TIPOS)
def test_crear_con_cada_tipo_de_control(m, tipo):
    respuesta = m.operador.post(URL, _datos(m, tipo_control_stock=tipo), format="json")

    assert respuesta.status_code == 201, respuesta.data
    assert respuesta.data["tipo_control_stock"] == tipo
    assert Producto.objects.get(pk=respuesta.data["id"]).tipo_control_stock == tipo


def test_sin_enviar_el_tipo_el_producto_queda_sin_control(m):
    respuesta = m.operador.post(URL, _datos(m), format="json")

    assert respuesta.status_code == 201
    assert respuesta.data["tipo_control_stock"] == CONTROL.NINGUNO


@pytest.mark.parametrize("valor", ["OTRO", "", "producto", "Producto terminado", None])
def test_un_valor_invalido_se_rechaza_al_crear(m, valor):
    respuesta = m.operador.post(URL, _datos(m, tipo_control_stock=valor), format="json")

    assert respuesta.status_code == 400
    assert respuesta.data["tipo_control_stock"] == ["Elige un tipo de control de stock válido."]
    assert not Producto.objects.exists()


def test_editar_cambia_el_tipo_de_control(m):
    producto = _producto(m)

    for tipo in (CONTROL.PRODUCTO, CONTROL.INSUMOS, CONTROL.NINGUNO):
        respuesta = m.operador.patch(f"{URL}{producto.pk}/", {"tipo_control_stock": tipo}, format="json")
        assert respuesta.status_code == 200, respuesta.data
        assert respuesta.data["tipo_control_stock"] == tipo
        producto.refresh_from_db()
        assert producto.tipo_control_stock == tipo


def test_editar_otros_campos_no_toca_el_tipo(m):
    producto = _producto(m, CONTROL.INSUMOS)

    respuesta = m.operador.patch(f"{URL}{producto.pk}/", {"nombre": "Doble"}, format="json")

    assert respuesta.status_code == 200
    assert respuesta.data["tipo_control_stock"] == CONTROL.INSUMOS
    producto.refresh_from_db()
    assert (producto.nombre, producto.tipo_control_stock) == ("Doble", CONTROL.INSUMOS)


def test_un_valor_invalido_al_editar_no_cambia_nada(m):
    producto = _producto(m, CONTROL.PRODUCTO)

    respuesta = m.operador.patch(f"{URL}{producto.pk}/", {"tipo_control_stock": "OTRO"}, format="json")

    assert respuesta.status_code == 400
    producto.refresh_from_db()
    assert producto.tipo_control_stock == CONTROL.PRODUCTO


def test_el_put_completo_sin_el_tipo_tambien_lo_conserva(m):
    producto = _producto(m, CONTROL.PRODUCTO)

    respuesta = m.operador.put(f"{URL}{producto.pk}/", _datos(m, nombre="Nueva"), format="json")

    assert respuesta.status_code == 200
    producto.refresh_from_db()
    assert producto.tipo_control_stock == CONTROL.PRODUCTO


def test_el_listado_devuelve_el_tipo_de_cada_producto(m):
    a = _producto(m, CONTROL.PRODUCTO, nombre="A")
    b = _producto(m, CONTROL.INSUMOS, nombre="B")
    c = _producto(m, CONTROL.NINGUNO, nombre="C")

    respuesta = m.operador.get(URL)

    tipos = {p["id"]: p["tipo_control_stock"] for p in respuesta.data}
    assert tipos == {a.pk: CONTROL.PRODUCTO, b.pk: CONTROL.INSUMOS, c.pk: CONTROL.NINGUNO}


def test_los_productos_existentes_son_sin_control_y_siguen_funcionando(m):
    # an old product: created without choosing a type, with the default stock row
    antiguo = Producto.objects.create(
        categoria=m.categoria, nombre="Antiguo", precio_base=9000, tiempo_preparacion=5
    )
    InventarioProducto.objects.create(sede=m.sede, producto=antiguo, disponible=True)

    assert m.operador.get(URL).data[0]["tipo_control_stock"] == CONTROL.NINGUNO
    assert _menu(m)[antiguo.pk]["disponible"] is True
    assert _validar(m, antiguo)["valido"] is True
    assert _comprar(m, antiguo).status_code == 201


# --- Producto terminado: con stock 0 no se vende ----------------------------------------

def test_producto_terminado_sin_stock_sale_no_disponible_en_el_menu(m):
    producto = _producto(m, CONTROL.PRODUCTO, stock=0)

    assert _menu(m)[producto.pk]["disponible"] is False

    InventarioProducto.objects.filter(producto=producto).update(stock_actual=3)
    assert _menu(m)[producto.pk]["disponible"] is True


def test_producto_terminado_sin_stock_no_pasa_la_validacion_del_carrito(m):
    producto = _producto(m, CONTROL.PRODUCTO, stock=0)

    datos = _validar(m, producto)

    assert datos["valido"] is False
    assert datos["no_disponibles"] == [{"id": producto.pk, "nombre": "Clásica"}]
    assert datos["retirados"] == []


def test_producto_terminado_sin_stock_no_se_puede_comprar(m):
    producto = _producto(m, CONTROL.PRODUCTO, stock=0)

    respuesta = _comprar(m, producto)

    assert respuesta.status_code == 400
    assert not Pedido.objects.exists()


def test_producto_terminado_con_stock_se_compra_y_se_descuenta(m):
    producto = _producto(m, CONTROL.PRODUCTO, stock=5)

    respuesta = _comprar(m, producto, cantidad=2)

    assert respuesta.status_code == 201, respuesta.data
    assert InventarioProducto.objects.get(producto=producto).stock_actual == 3


def test_producto_terminado_no_deja_comprar_mas_de_lo_que_hay(m):
    producto = _producto(m, CONTROL.PRODUCTO, stock=1)

    assert _comprar(m, producto, cantidad=2).status_code == 400
    assert InventarioProducto.objects.get(producto=producto).stock_actual == 1


def test_sin_control_con_stock_cero_se_sigue_vendiendo_y_no_descuenta(m):
    producto = _producto(m, CONTROL.NINGUNO, stock=0)

    assert _menu(m)[producto.pk]["disponible"] is True
    assert _comprar(m, producto, cantidad=3).status_code == 201
    assert InventarioProducto.objects.get(producto=producto).stock_actual == 0


# --- Por insumos: depende de los ingredientes de su receta ------------------------------

def test_por_insumos_depende_de_la_existencia_de_sus_ingredientes(m):
    producto = _producto(m, CONTROL.INSUMOS)
    inventario = _receta(m, producto, stock=0)

    assert _menu(m)[producto.pk]["disponible"] is False
    assert _validar(m, producto)["valido"] is False
    assert _comprar(m, producto).status_code == 400

    inventario.stock_actual = 10
    inventario.save()
    assert _menu(m)[producto.pk]["disponible"] is True
    assert _validar(m, producto)["valido"] is True


def test_por_insumos_un_ingrediente_no_disponible_en_la_sede_bloquea(m):
    producto = _producto(m, CONTROL.INSUMOS)
    inventario = _receta(m, producto, stock=10)
    inventario.disponible = False
    inventario.save()

    assert _menu(m)[producto.pk]["disponible"] is False


def test_por_insumos_la_compra_descuenta_los_ingredientes_y_no_el_producto(m):
    producto = _producto(m, CONTROL.INSUMOS, stock=0)
    inventario = _receta(m, producto, stock=10, cantidad=2)

    respuesta = _comprar(m, producto, cantidad=3)

    assert respuesta.status_code == 201, respuesta.data
    inventario.refresh_from_db()
    assert inventario.stock_actual == 4
    assert InventarioProducto.objects.get(producto=producto).stock_actual == 0


# --- Cambiar el tipo cambia la disponibilidad (de punta a punta) ---------------------------

def test_pasar_un_producto_a_producto_terminado_lo_agota_si_no_tiene_stock(m):
    producto = _producto(m, CONTROL.NINGUNO, stock=0)
    assert _menu(m)[producto.pk]["disponible"] is True

    respuesta = m.operador.patch(f"{URL}{producto.pk}/", {"tipo_control_stock": "PRODUCTO"}, format="json")

    assert respuesta.status_code == 200
    assert _menu(m)[producto.pk]["disponible"] is False
