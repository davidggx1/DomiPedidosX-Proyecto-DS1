"""HU-26 · El cliente vuelve a cargar un pedido anterior en su carrito."""
from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from inventario.models import InventarioProducto
from menu.models import Adicion, CategoriaMenu, Insumo, Producto, ProductoAdicion, ProductoInsumo, ProductoTamano
from pedidos.models import DetallePedido, DetallePedidoAdicion, DetallePedidoExclusion, EstadoPedido as E, Pedido
from promociones.models import Combo, ComboProducto, ComboSede
from sedes.models import Ciudad, Sede
from usuarios.models import Cliente, Usuario

pytestmark = pytest.mark.django_db


def _sede(nombre="Centro"):
    ciudad, _ = Ciudad.objects.get_or_create(nombre="Cali")
    return Sede.objects.create(
        ciudad=ciudad, nombre=nombre, direccion="Cra 1 # 2-3", activa=True, latitud=3.45,
        longitud=-76.53, barrio="Centro", telefono="3000000000", correo=f"{nombre.lower()}@domi.com",
    )


def _cliente(email, celular="3001234567"):
    usuario = Usuario.objects.create_user(username=email, email=email, password="ClaveSegura2026")
    return Cliente.objects.create(
        usuario=usuario, tipo_documento="CC", num_documento=email[:10], nombres="Ana",
        apellidos="Gómez", celular=celular, fecha_nacimiento=date(2000, 1, 1),
    )


def _http(cliente):
    api = APIClient()
    api.force_authenticate(cliente.usuario)
    return api


@pytest.fixture
def menu():
    sede = _sede()
    categoria = CategoriaMenu.objects.create(nombre="Hamburguesas")
    hamburguesa = Producto.objects.create(
        categoria=categoria, nombre="Hamburguesa", precio_base=Decimal("20000"), tiempo_preparacion=15
    )
    gaseosa = Producto.objects.create(
        categoria=categoria, nombre="Gaseosa", precio_base=Decimal("4000"), tiempo_preparacion=1
    )
    for producto in (hamburguesa, gaseosa):
        InventarioProducto.objects.create(sede=sede, producto=producto, disponible=True)
    doble = ProductoTamano.objects.create(producto=hamburguesa, nombre="Doble", precio_adicional=Decimal("8000"))
    cebolla_insumo = Insumo.objects.create(nombre="Cebolla", unidad_medida="g")
    cebolla = ProductoInsumo.objects.create(
        producto=hamburguesa, insumo=cebolla_insumo, cantidad_necesaria=Decimal("20"), es_excluible=True
    )
    queso = Adicion.objects.create(
        nombre="Queso extra", precio=Decimal("3000"), insumo=Insumo.objects.create(nombre="Queso", unidad_medida="g")
    )
    ProductoAdicion.objects.create(producto=hamburguesa, adicion=queso, max_cantidad=2)
    return {
        "sede": sede, "hamburguesa": hamburguesa, "gaseosa": gaseosa, "doble": doble,
        "cebolla": cebolla, "queso": queso,
    }


@pytest.fixture
def ana():
    return _cliente("ana@correo.com")


def _pedido(menu, cliente, estado=E.ENTREGADO):
    """Pedido de ayer: 2 hamburguesas dobles con 1 queso y sin cebolla + 3 gaseosas."""
    pedido = Pedido.objects.create(sede=menu["sede"], cliente=cliente, numero_pedido="P-1", estado=estado)
    hamburguesas = DetallePedido.objects.create(
        pedido=pedido, producto=menu["hamburguesa"], producto_tamano=menu["doble"], cantidad=2,
        precio_unitario=Decimal("29000"), subtotal=Decimal("58000"),
    )
    DetallePedidoAdicion.objects.create(
        detalle_pedido=hamburguesas, adicion=menu["queso"], cantidad=1, precio_unitario=Decimal("3000")
    )
    DetallePedidoExclusion.objects.create(
        detalle_pedido=hamburguesas, insumo=menu["cebolla"].insumo, nombre_insumo="Cebolla"
    )
    DetallePedido.objects.create(
        pedido=pedido, producto=menu["gaseosa"], cantidad=3, precio_unitario=Decimal("3500"),
        subtotal=Decimal("10500"),
    )
    return pedido


def _repetir(cliente, pedido):
    return _http(cliente).post(f"/api/pedidos/mios/{pedido.pk}/repetir/")


def test_arma_las_lineas_con_la_misma_personalizacion(menu, ana):
    respuesta = _repetir(ana, _pedido(menu, ana))

    assert respuesta.status_code == 200, respuesta.data
    assert respuesta.data["sede"] == {"id": menu["sede"].pk, "nombre": "Centro"}
    assert respuesta.data["no_disponibles"] == []
    hamburguesa, gaseosa = respuesta.data["lineas"]
    assert hamburguesa["producto"]["id"] == menu["hamburguesa"].pk
    assert hamburguesa["producto"]["nombre"] == "Hamburguesa"
    assert hamburguesa["tamano"] == {"id": menu["doble"].pk, "nombre": "Doble", "precio_adicional": "8000.00"}
    assert hamburguesa["adiciones"] == [
        {"adicion": menu["queso"].pk, "nombre": "Queso extra", "precio": "3000.00", "cantidad": 1}
    ]
    assert hamburguesa["exclusiones"] == [{"id": menu["cebolla"].pk, "nombre": "Cebolla"}]
    assert hamburguesa["cantidad"] == 2
    assert gaseosa["cantidad"] == 3 and gaseosa["tamano"] is None


def test_usa_el_precio_de_hoy(menu, ana):
    pedido = _pedido(menu, ana)
    Producto.objects.filter(pk=menu["gaseosa"].pk).update(precio_base=Decimal("5000"))

    lineas = _repetir(ana, pedido).data["lineas"]

    assert lineas[0]["precio_unitario"] == "31000.00"  # 20000 + 8000 + 3000
    assert lineas[1]["precio_unitario"] == "5000.00"  # se pagó 3500


def test_lo_que_ya_no_se_puede_pedir_queda_fuera_con_su_motivo(menu, ana):
    pedido = _pedido(menu, ana)
    Producto.objects.filter(pk=menu["gaseosa"].pk).update(activo=False)
    Adicion.objects.filter(pk=menu["queso"].pk).update(activa=False)

    datos = _repetir(ana, pedido).data

    assert datos["lineas"] == []
    assert [item["nombre"] for item in datos["no_disponibles"]] == ["Hamburguesa (Doble)", "Gaseosa"]
    assert datos["no_disponibles"][0]["motivo"] == "Una de las adiciones no está disponible para este producto."
    assert "no existe o no está activo" in datos["no_disponibles"][1]["motivo"]


def test_producto_marcado_no_disponible_en_la_sede(menu, ana):
    pedido = _pedido(menu, ana)
    InventarioProducto.objects.filter(producto=menu["gaseosa"]).update(disponible=False)

    datos = _repetir(ana, pedido).data

    assert len(datos["lineas"]) == 1
    assert datos["no_disponibles"][0]["nombre"] == "Gaseosa"


def test_sin_stock_suficiente_para_la_cantidad(menu, ana):
    pedido = _pedido(menu, ana)
    Producto.objects.filter(pk=menu["gaseosa"].pk).update(tipo_control_stock=Producto.TipoControlStock.PRODUCTO)
    InventarioProducto.objects.filter(producto=menu["gaseosa"]).update(stock_actual=2)

    motivo = _repetir(ana, pedido).data["no_disponibles"][0]["motivo"]

    assert "Solo quedan 2" in motivo


def _combo(menu, **cambios):
    # Los combos (HU-85) respetan las existencias de Inventario aunque el producto no las controle
    InventarioProducto.objects.filter(producto=menu["gaseosa"]).update(stock_actual=50)
    hoy = timezone.localdate()
    combo = Combo.objects.create(
        nombre="Combo Clásico", descripcion="Hamburguesa + gaseosa", precio=Decimal("21000"),
        fecha_inicio=hoy - timedelta(days=5), fecha_vencimiento=hoy + timedelta(days=5),
    )
    ComboProducto.objects.create(combo=combo, producto=menu["gaseosa"], cantidad=1)
    ComboSede.objects.create(combo=combo, sede=menu["sede"], **cambios)
    return combo


def _pedido_combo(menu, cliente, combo, cantidad=2):
    numero = f"C-{Pedido.objects.count() + 1}"
    pedido = Pedido.objects.create(sede=menu["sede"], cliente=cliente, numero_pedido=numero, estado=E.ENTREGADO)
    DetallePedido.objects.create(
        pedido=pedido, combo=combo, cantidad=cantidad, precio_unitario=Decimal("20000"), subtotal=Decimal("40000")
    )
    return pedido


def test_combo_vigente_vuelve_con_su_precio_de_hoy(menu, ana):
    combo = _combo(menu)

    linea = _repetir(ana, _pedido_combo(menu, ana, combo)).data["lineas"][0]

    assert linea["combo"]["id"] == combo.pk
    assert linea["combo"]["productos_incluidos"] == [
        {"producto_id": menu["gaseosa"].pk, "nombre": "Gaseosa", "cantidad": 1}
    ]
    assert linea["cantidad"] == 2 and linea["precio_unitario"] == "21000.00"


def test_combo_vencido_o_sin_cupo_queda_fuera(menu, ana):
    vencido = _combo(menu)
    Combo.objects.filter(pk=vencido.pk).update(fecha_vencimiento=timezone.localdate() - timedelta(days=1),
                                               fecha_inicio=timezone.localdate() - timedelta(days=9))
    con_cupo = _combo(menu, cupo_max_diario=1)

    vencido_resp = _repetir(ana, _pedido_combo(menu, ana, vencido)).data
    cupo_resp = _repetir(ana, _pedido_combo(menu, ana, con_cupo, cantidad=2)).data

    assert vencido_resp["no_disponibles"] == [{"nombre": "Combo Clásico", "motivo": "El combo está vencido."}]
    assert cupo_resp["no_disponibles"][0]["motivo"] == "Solo quedan 1 unidades disponibles hoy."


def test_tambien_un_pedido_cancelado(menu, ana):
    assert _repetir(ana, _pedido(menu, ana, estado=E.CANCELADO)).status_code == 200


def test_solo_pedidos_propios(menu, ana):
    otra = _cliente("otra@correo.com", "3007654321")

    assert _repetir(otra, _pedido(menu, ana)).status_code == 404


def test_sede_inactiva_es_409(menu, ana):
    pedido = _pedido(menu, ana)
    Sede.objects.filter(pk=menu["sede"].pk).update(activa=False)

    respuesta = _repetir(ana, pedido)

    assert respuesta.status_code == 409
    assert "Centro ya no está recibiendo pedidos" in respuesta.data["detail"]


def test_solo_clientes(menu, ana):
    pedido = _pedido(menu, ana)
    assert APIClient().post(f"/api/pedidos/mios/{pedido.pk}/repetir/").status_code == 401


def test_no_crea_pedidos(menu, ana):
    pedido = _pedido(menu, ana)
    _repetir(ana, pedido)
    assert Pedido.objects.count() == 1
