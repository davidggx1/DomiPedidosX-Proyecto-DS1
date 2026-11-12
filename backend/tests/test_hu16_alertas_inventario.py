"""HU-16: low stock alerts."""
from datetime import date
from decimal import Decimal
from types import SimpleNamespace

import pytest
from django.contrib.auth.models import Group
from django.db import IntegrityError, transaction
from rest_framework.test import APIClient

from inventario.alertas import datos_alerta
from inventario.models import AlertaInventario, InventarioInsumo, InventarioProducto
from menu.models import CategoriaMenu, Insumo, Producto
from pedidos.models import EstadoPedido, Pedido
from sedes.models import Ciudad, Sede, ZonaCobertura
from usuarios.models import Cliente, DireccionEntrega, Empleado, Usuario

pytestmark = pytest.mark.django_db

ALERTAS = "/api/inventario/alertas/"
CONTROL = Producto.TipoControlStock
ACTIVA = AlertaInventario.Estado.ACTIVA
RESUELTA = AlertaInventario.Estado.RESUELTA


def _usuario(email, rol=None, sede=None):
    usuario = Usuario.objects.create_user(
        username=email, email=email, password="ClaveSegura2026"
    )
    if rol:
        usuario.groups.add(Group.objects.get_or_create(name=rol)[0])
    if sede or rol == "administrador":
        Empleado.objects.create(
            usuario=usuario, sede=sede, tipo_documento="CC", num_documento=email[:10],
            nombres="N", apellidos="A", celular="3001234567", direccion="Calle 4",
        )
    return usuario


def _http(usuario):
    c = APIClient()
    c.force_authenticate(user=usuario)
    return c


def _sede(nombre, ciudad):
    return Sede.objects.create(
        ciudad=ciudad, nombre=nombre, direccion="Calle 1 # 2-3", latitud=3.45,
        longitud=-76.53, barrio="Granada", telefono="3000000000", correo="s@correo.com",
    )


def _producto(nombre="Hamburguesa", control=CONTROL.PRODUCTO):
    categoria, _ = CategoriaMenu.objects.get_or_create(nombre="Platos")
    return Producto.objects.create(
        categoria=categoria, nombre=nombre, precio_base=Decimal("20000"),
        tiempo_preparacion=15, tipo_control_stock=control,
    )


def _poner_stock(inv, valor):
    inv.stock_actual = valor
    inv.save()


def _alertas(**filtros):
    return AlertaInventario.objects.filter(**filtros)


@pytest.fixture
def m():
    ciudad = Ciudad.objects.create(nombre="Cali")
    sede = _sede("Norte", ciudad)
    otra_sede = _sede("Sur", ciudad)
    producto = _producto()
    inv = InventarioProducto.objects.create(
        sede=sede, producto=producto, stock_actual=10, stock_minimo=5
    )
    return SimpleNamespace(
        ciudad=ciudad, sede=sede, otra_sede=otra_sede, producto=producto, inv=inv,
        operador=_usuario("op@correo.com", "operador", sede),
        operador_sur=_usuario("op2@correo.com", "operador", otra_sede),
        admin=_usuario("ad@correo.com", "administrador"),
    )


# --- Criterio 1: el operador fija el umbral (y cambiarlo re-evalúa la alerta) -------

def test_el_operador_fija_el_minimo_y_se_evalua_de_nuevo(m):
    c = _http(m.operador)
    url = f"/api/inventario/productos/{m.inv.pk}/"
    assert not _alertas().exists()

    # 10 in stock, minimum raised to 12: it is under the new minimum
    assert c.patch(url, {"stock_minimo": 12}, format="json").status_code == 200
    assert _alertas(estado=ACTIVA).count() == 1

    # minimum lowered to 3: the stock is over it again
    assert c.patch(url, {"stock_minimo": 3}, format="json").status_code == 200
    assert _alertas(estado=ACTIVA).count() == 0
    assert _alertas(estado=RESUELTA).count() == 1


# --- Criterio 2: al alcanzar o bajar del umbral, alerta con producto y stock ----------

@pytest.mark.parametrize("stock", [5, 4, 0])
def test_alerta_al_alcanzar_o_bajar_del_minimo(m, stock):
    _poner_stock(m.inv, stock)

    alerta = _alertas(estado=ACTIVA).get()
    datos = datos_alerta(alerta)
    assert datos["nombre"] == "Hamburguesa"
    assert datos["tipo"] == "producto"
    assert datos["stock_actual"] == stock
    assert datos["stock_minimo"] == 5
    assert datos["sede"] == m.sede.pk


def test_sobre_el_minimo_no_hay_alerta(m):
    _poner_stock(m.inv, 6)

    assert not _alertas().exists()


def test_alerta_de_insumo_con_decimales_y_unidad(m):
    insumo = Insumo.objects.create(nombre="Harina", unidad_medida="kg")
    inv = InventarioInsumo.objects.create(
        sede=m.sede, insumo=insumo, stock_actual=Decimal("8"), stock_minimo=Decimal("3")
    )

    _poner_stock(inv, Decimal("2.5"))

    datos = datos_alerta(_alertas(estado=ACTIVA).get())
    assert datos["tipo"] == "insumo"
    assert (datos["nombre"], datos["unidad"]) == ("Harina", "kg")
    assert datos["stock_actual"] == 2.5 and datos["stock_minimo"] == 3


def test_minimo_cero_alerta_cuando_se_agota(m):
    m.inv.stock_minimo = 0
    m.inv.stock_actual = 1
    m.inv.save()
    assert not _alertas().exists()

    _poner_stock(m.inv, 0)

    assert _alertas(estado=ACTIVA).count() == 1


@pytest.mark.parametrize("control", [CONTROL.NINGUNO, CONTROL.INSUMOS])
def test_productos_que_no_llevan_su_propio_stock_no_alertan(m, control):
    otro = _producto("Combo", control)
    inv = InventarioProducto.objects.create(
        sede=m.sede, producto=otro, stock_actual=10, stock_minimo=5
    )

    _poner_stock(inv, 0)

    assert not _alertas(producto=otro).exists()


def test_guardar_otro_campo_no_vuelve_a_evaluar(m):
    # the stock is under the minimum without going through the receiver
    InventarioProducto.objects.filter(pk=m.inv.pk).update(stock_actual=1)
    m.inv.refresh_from_db()

    m.inv.disponible = False
    m.inv.save(update_fields=["disponible"])

    assert not _alertas().exists()


# --- Criterio 3: sin alertas duplicadas mientras siga por debajo del mínimo -----------

def test_no_se_duplica_mientras_siga_por_debajo(m):
    for stock in (5, 4, 3, 1, 0, 0):
        _poner_stock(m.inv, stock)

    assert _alertas().count() == 1
    alerta = _alertas().get()
    assert alerta.estado == ACTIVA
    assert alerta.stock_al_disparar == 5


def test_la_base_de_datos_impide_dos_alertas_activas_del_mismo_item(m):
    _poner_stock(m.inv, 4)

    with pytest.raises(IntegrityError), transaction.atomic():
        AlertaInventario.objects.create(
            sede=m.sede, producto=m.producto, stock_al_disparar=4, stock_minimo_al_disparar=5
        )


def test_una_alerta_necesita_un_producto_o_un_insumo_pero_no_ambos(m):
    insumo = Insumo.objects.create(nombre="Harina", unidad_medida="kg")
    for datos in ({}, {"producto": m.producto, "insumo": insumo}):
        with pytest.raises(IntegrityError), transaction.atomic():
            AlertaInventario.objects.create(
                sede=m.sede, stock_al_disparar=1, stock_minimo_al_disparar=5, **datos
            )


def test_cada_sede_tiene_su_propia_alerta_del_mismo_producto(m):
    otro_inv = InventarioProducto.objects.create(
        sede=m.otra_sede, producto=m.producto, stock_actual=10, stock_minimo=5
    )

    _poner_stock(m.inv, 2)
    _poner_stock(otro_inv, 2)

    assert _alertas(estado=ACTIVA).count() == 2


# --- Criterio 4: se resuelve sola cuando el stock supera el umbral -------------------

def test_se_resuelve_cuando_el_stock_supera_el_minimo(m):
    _poner_stock(m.inv, 3)

    _poner_stock(m.inv, 5)  # exactly the minimum: still active
    assert _alertas(estado=ACTIVA).count() == 1

    _poner_stock(m.inv, 6)
    alerta = _alertas().get()
    assert alerta.estado == RESUELTA
    assert alerta.resuelta_en is not None


def test_vuelve_a_alertar_despues_de_resuelta(m):
    _poner_stock(m.inv, 3)
    _poner_stock(m.inv, 8)
    _poner_stock(m.inv, 4)

    assert _alertas().count() == 2
    assert _alertas(estado=ACTIVA).count() == 1
    assert _alertas(estado=RESUELTA).count() == 1


def test_quitar_las_existencias_cierra_la_alerta(m):
    _poner_stock(m.inv, 2)

    m.inv.delete()

    assert _alertas().get().estado == RESUELTA


# --- Por los caminos reales del stock: confirmar y cancelar un pedido -----------------

def test_confirmar_un_pedido_dispara_y_cancelarlo_resuelve(m):
    ZonaCobertura.objects.create(
        sede=m.sede, nombre="Zona 1", radio=5, centro_latitud=3.45, centro_longitud=-76.53,
        tarifa_domicilio=Decimal("3000"), tiempo_estimado=40, pedido_minimo=Decimal("0"),
    )
    usuario = _usuario("cli@correo.com")
    cliente = Cliente.objects.create(
        usuario=usuario, tipo_documento="CC", num_documento="1", nombres="Ana",
        apellidos="Prueba", celular="3001234567", fecha_nacimiento=date(2000, 1, 1),
    )
    direccion = DireccionEntrega.objects.create(
        ciudad=m.ciudad, cliente=cliente, direccion="Calle 5 # 6-7", latitud=3.46, longitud=-76.53,
    )
    c = _http(usuario)
    _poner_stock(m.inv, 7)

    r = c.post(
        "/api/pedidos/confirmar/",
        {
            "sede_id": m.sede.pk, "direccion_id": direccion.pk, "metodo_pago": "tarjeta",
            "items": [{"producto_id": m.producto.pk, "cantidad": 2}],
        },
        format="json",
    )
    assert r.status_code == 201, r.data
    # 7 - 2 = 5, it reaches the minimum
    assert _alertas(estado=ACTIVA).get().producto == m.producto

    pedido = Pedido.objects.latest("pk")
    assert c.post(f"/api/pedidos/{pedido.pk}/cancelar/").status_code == 200
    # the stock is back to 7, over the minimum
    assert _alertas(estado=ACTIVA).count() == 0
    assert _alertas(estado=RESUELTA).count() == 1
    assert Pedido.objects.get(pk=pedido.pk).estado == EstadoPedido.CANCELADO


# --- Endpoint para el panel ------------------------------------------------------------

def test_endpoint_lista_las_alertas_activas_de_la_sede_del_operador(m):
    otro_inv = InventarioProducto.objects.create(
        sede=m.otra_sede, producto=m.producto, stock_actual=10, stock_minimo=5
    )
    _poner_stock(m.inv, 2)
    _poner_stock(otro_inv, 1)

    r = _http(m.operador).get(ALERTAS)

    assert r.status_code == 200
    assert [a["sede"] for a in r.data] == [m.sede.pk]
    assert (r.data[0]["nombre"], r.data[0]["stock_actual"], r.data[0]["stock_minimo"]) == (
        "Hamburguesa", 2, 5,
    )
    assert r.data[0]["estado"] == "activa"


def test_endpoint_administrador_ve_todas_o_una_sede(m):
    otro_inv = InventarioProducto.objects.create(
        sede=m.otra_sede, producto=m.producto, stock_actual=10, stock_minimo=5
    )
    _poner_stock(m.inv, 2)
    _poner_stock(otro_inv, 1)
    c = _http(m.admin)

    assert len(c.get(ALERTAS).data) == 2
    assert [a["sede"] for a in c.get(ALERTAS, {"sede": m.otra_sede.pk}).data] == [m.otra_sede.pk]


def test_endpoint_historial_de_resueltas(m):
    _poner_stock(m.inv, 2)
    _poner_stock(m.inv, 9)
    c = _http(m.operador)

    assert c.get(ALERTAS).data == []
    resueltas = c.get(ALERTAS, {"estado": "resuelta"}).data
    assert len(resueltas) == 1 and resueltas[0]["resuelta_en"] is not None
    assert len(c.get(ALERTAS, {"estado": "todas"}).data) == 1


def test_endpoint_permisos_y_parametros(m):
    assert APIClient().get(ALERTAS).status_code == 401
    cliente = _usuario("cli@correo.com")
    assert _http(cliente).get(ALERTAS).status_code == 403
    assert _http(m.operador).get(ALERTAS, {"estado": "otra"}).status_code == 400
    assert _http(m.operador).get(ALERTAS, {"sede": "x"}).status_code == 400
