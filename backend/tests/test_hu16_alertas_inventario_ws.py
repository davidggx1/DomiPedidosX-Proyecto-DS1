"""HU-16: low stock alerts reach the operator by WebSocket."""
from decimal import Decimal

import pytest
from asgiref.sync import sync_to_async
from channels.testing import WebsocketCommunicator
from django.contrib.auth.models import Group
from rest_framework_simplejwt.tokens import AccessToken

from config.asgi import application
from inventario import alertas
from inventario.models import AlertaInventario, InventarioProducto
from menu.models import CategoriaMenu, Producto
from sedes.models import Ciudad, Sede
from usuarios.models import Empleado, Usuario

pytestmark = [pytest.mark.asyncio, pytest.mark.django_db(transaction=True)]


def _sede(nombre):
    ciudad, _ = Ciudad.objects.get_or_create(nombre="Cali")
    return Sede.objects.create(
        ciudad=ciudad, nombre=nombre, direccion="Calle 1 # 2-3", latitud=3.45,
        longitud=-76.53, barrio="Granada", telefono="3000000000", correo="s@correo.com",
    )


def _personal(rol, email, sede=None):
    usuario = Usuario.objects.create_user(username=email, email=email, password="ClaveSegura2026")
    usuario.groups.add(Group.objects.get_or_create(name=rol)[0])
    if sede:
        Empleado.objects.create(
            usuario=usuario, sede=sede, tipo_documento="CC", num_documento=email[:10],
            nombres="N", apellidos="A", celular="3001234567", direccion="Calle 4",
        )
    return usuario


def _existencias(sede, stock=10, minimo=5, nombre="Hamburguesa"):
    categoria, _ = CategoriaMenu.objects.get_or_create(nombre="Platos")
    producto = Producto.objects.create(
        categoria=categoria, nombre=nombre, precio_base=Decimal("20000"), tiempo_preparacion=15,
        tipo_control_stock=Producto.TipoControlStock.PRODUCTO,
    )
    return InventarioProducto.objects.create(
        sede=sede, producto=producto, stock_actual=stock, stock_minimo=minimo
    )


def _poner_stock(inv, valor):
    inv.stock_actual = valor
    inv.save()


async def _conectar(usuario):
    token = str(AccessToken.for_user(usuario))
    canal = WebsocketCommunicator(application, f"/ws/pedidos/entrantes/?token={token}")
    assert (await canal.connect())[0]
    return canal


async def _operador_conectado(sede, email="op@correo.com"):
    operador = await sync_to_async(_personal)("operador", email, sede)
    return await _conectar(operador)


async def _evento(canal):
    datos = await canal.receive_json_from(timeout=5)
    assert datos["tipo"] == "alerta_inventario"
    return datos


async def test_avisa_al_operador_producto_y_stock_actual_al_llegar_al_minimo():
    sede = await sync_to_async(_sede)("Norte")
    inv = await sync_to_async(_existencias)(sede, stock=10, minimo=5)
    canal = await _operador_conectado(sede)

    await sync_to_async(_poner_stock)(inv, 8)
    assert await canal.receive_nothing(timeout=0.5)

    await sync_to_async(_poner_stock)(inv, 5)
    datos = await _evento(canal)

    assert datos["transicion"] == "creada"
    alerta = datos["alerta"]
    assert (alerta["nombre"], alerta["stock_actual"], alerta["stock_minimo"]) == ("Hamburguesa", 5, 5)
    assert (alerta["tipo"], alerta["estado"], alerta["sede"]) == ("producto", "activa", sede.pk)
    await canal.disconnect()


async def test_no_repite_la_alerta_mientras_siga_por_debajo():
    sede = await sync_to_async(_sede)("Norte")
    inv = await sync_to_async(_existencias)(sede)
    canal = await _operador_conectado(sede)

    await sync_to_async(_poner_stock)(inv, 5)
    primera = await _evento(canal)
    await sync_to_async(_poner_stock)(inv, 3)
    segunda = await _evento(canal)

    assert primera["transicion"] == "creada"
    # the same alert with the new stock, not a new one
    assert segunda["transicion"] == "actualizada"
    assert segunda["alerta"]["id"] == primera["alerta"]["id"]
    assert segunda["alerta"]["stock_actual"] == 3
    assert await sync_to_async(AlertaInventario.objects.count)() == 1
    await canal.disconnect()


async def test_avisa_que_se_resolvio_al_superar_el_minimo():
    sede = await sync_to_async(_sede)("Norte")
    inv = await sync_to_async(_existencias)(sede)
    canal = await _operador_conectado(sede)
    await sync_to_async(_poner_stock)(inv, 4)
    creada = await _evento(canal)

    await sync_to_async(_poner_stock)(inv, 9)
    datos = await _evento(canal)

    assert datos["transicion"] == "resuelta"
    assert datos["alerta"]["id"] == creada["alerta"]["id"]
    assert datos["alerta"]["estado"] == "resuelta"
    assert datos["alerta"]["resuelta_en"] is not None
    await canal.disconnect()


async def test_la_alerta_solo_llega_a_los_operadores_de_su_sede():
    norte = await sync_to_async(_sede)("Norte")
    sur = await sync_to_async(_sede)("Sur")
    inv = await sync_to_async(_existencias)(norte)
    canal_norte = await _operador_conectado(norte, "op_norte@correo.com")
    canal_sur = await _operador_conectado(sur, "op_sur@correo.com")
    admin = await sync_to_async(_personal)("administrador", "ad@correo.com")
    canal_admin = await _conectar(admin)

    await sync_to_async(_poner_stock)(inv, 1)

    assert (await _evento(canal_norte))["alerta"]["sede"] == norte.pk
    assert await canal_sur.receive_nothing(timeout=0.5)
    assert await canal_admin.receive_nothing(timeout=0.5)
    for canal in (canal_norte, canal_sur, canal_admin):
        await canal.disconnect()


async def test_un_fallo_del_canal_no_rompe_el_cambio_de_stock(monkeypatch):
    sede = await sync_to_async(_sede)("Norte")
    inv = await sync_to_async(_existencias)(sede)

    def canal_roto():
        raise RuntimeError("redis caido")

    monkeypatch.setattr(alertas, "get_channel_layer", canal_roto)

    await sync_to_async(_poner_stock)(inv, 1)

    await inv.arefresh_from_db()
    assert inv.stock_actual == 1
    assert await AlertaInventario.objects.filter(estado="activa").aexists()
