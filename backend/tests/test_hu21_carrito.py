"""HU-21 · Validación y precio de las líneas personalizadas del carrito."""
from decimal import Decimal

import pytest
from rest_framework.test import APIClient

from inventario.models import InventarioProducto
from menu.models import (
    Adicion,
    CategoriaMenu,
    Insumo,
    Producto,
    ProductoAdicion,
    ProductoInsumo,
    ProductoTamano,
)
from sedes.models import Ciudad, Sede


def crear_sede(nombre):
    ciudad, _ = Ciudad.objects.get_or_create(nombre="Cali")
    return Sede.objects.create(
        ciudad=ciudad, nombre=nombre, direccion="Cra 1 # 2-3", activa=True,
        latitud=3.45, longitud=-76.53, barrio="Centro",
        telefono="3000000000", correo=f"{nombre.lower()}@domi.com",
    )


@pytest.fixture
def menu(db):
    sede = crear_sede("Centro")
    categoria = CategoriaMenu.objects.create(nombre="Hamburguesas")
    producto = Producto.objects.create(
        categoria=categoria, nombre="Hamburguesa Clásica", precio_base=Decimal("20000"),
        tiempo_preparacion=15,
    )
    InventarioProducto.objects.create(sede=sede, producto=producto, disponible=True)

    personal = ProductoTamano.objects.create(producto=producto, nombre="Personal")
    doble = ProductoTamano.objects.create(
        producto=producto, nombre="Doble", precio_adicional=Decimal("8000")
    )

    cebolla = ProductoInsumo.objects.create(
        producto=producto, insumo=Insumo.objects.create(nombre="Cebolla", unidad_medida="g"),
        cantidad_necesaria=Decimal("20"), es_excluible=True,
    )
    pan = ProductoInsumo.objects.create(
        producto=producto, insumo=Insumo.objects.create(nombre="Pan", unidad_medida="unidad"),
        cantidad_necesaria=Decimal("1"), es_excluible=False,
    )

    queso = Adicion.objects.create(
        nombre="Queso extra", precio=Decimal("3000"),
        insumo=Insumo.objects.create(nombre="Queso", unidad_medida="g"),
    )
    ProductoAdicion.objects.create(producto=producto, adicion=queso, max_cantidad=2)

    return {
        "sede": sede, "producto": producto, "personal": personal, "doble": doble,
        "cebolla": cebolla, "pan": pan, "queso": queso, "categoria": categoria,
    }


def validar(sede, **linea):
    return APIClient().post(f"/api/menu/sedes/{sede.id}/carrito/linea/", linea, format="json")


def linea_base(menu, **cambios):
    datos = {"producto": menu["producto"].id, "tamano": menu["personal"].id, "cantidad": 1}
    datos.update(cambios)
    return datos


def test_precio_con_tamano_adiciones_y_cantidad(menu):
    respuesta = validar(
        menu["sede"],
        **linea_base(
            menu, tamano=menu["doble"].id, cantidad=2,
            adiciones=[{"adicion": menu["queso"].id, "cantidad": 2}],
        ),
    )

    assert respuesta.status_code == 200
    # 20000 + 8000 (doble) + 2 × 3000 (queso) = 34000 por unidad.
    assert respuesta.data == {"precio_unitario": "34000.00", "subtotal": "68000.00"}


def test_mismo_producto_con_variantes_distintas_da_lineas_distintas(menu):
    sencilla = validar(menu["sede"], **linea_base(menu))
    doble = validar(menu["sede"], **linea_base(menu, tamano=menu["doble"].id))
    con_queso = validar(
        menu["sede"], **linea_base(menu, adiciones=[{"adicion": menu["queso"].id, "cantidad": 1}])
    )

    precios = {r.data["precio_unitario"] for r in (sencilla, doble, con_queso)}
    assert precios == {"20000.00", "28000.00", "23000.00"}


def test_quitar_ingrediente_excluible_no_cambia_el_precio(menu):
    respuesta = validar(menu["sede"], **linea_base(menu, exclusiones=[menu["cebolla"].id]))

    assert respuesta.status_code == 200
    assert respuesta.data["precio_unitario"] == "20000.00"


def test_no_se_puede_quitar_un_ingrediente_obligatorio(menu):
    respuesta = validar(menu["sede"], **linea_base(menu, exclusiones=[menu["pan"].id]))

    assert respuesta.status_code == 400
    assert "Pan" in str(respuesta.data["exclusiones"])
    assert "obligatorio" in str(respuesta.data["exclusiones"])


def test_no_se_puede_quitar_un_ingrediente_de_otro_producto(menu):
    otro = Producto.objects.create(
        categoria=menu["categoria"], nombre="Perro", precio_base=Decimal("15000"),
        tiempo_preparacion=10,
    )
    ajeno = ProductoInsumo.objects.create(
        producto=otro, insumo=Insumo.objects.create(nombre="Salchicha", unidad_medida="unidad"),
        cantidad_necesaria=Decimal("1"), es_excluible=True,
    )

    respuesta = validar(menu["sede"], **linea_base(menu, exclusiones=[ajeno.id]))

    assert respuesta.status_code == 400
    assert "exclusiones" in respuesta.data


def test_adicion_que_supera_el_maximo(menu):
    respuesta = validar(
        menu["sede"], **linea_base(menu, adiciones=[{"adicion": menu["queso"].id, "cantidad": 3}])
    )

    assert respuesta.status_code == 400
    assert "máximo 2" in str(respuesta.data["adiciones"])


def test_adicion_que_no_es_del_producto(menu):
    tocineta = Adicion.objects.create(
        nombre="Tocineta", precio=Decimal("4000"),
        insumo=Insumo.objects.create(nombre="Tocino", unidad_medida="g"),
    )

    respuesta = validar(
        menu["sede"], **linea_base(menu, adiciones=[{"adicion": tocineta.id, "cantidad": 1}])
    )

    assert respuesta.status_code == 400
    assert "adiciones" in respuesta.data


def test_adicion_eliminada_no_se_acepta(menu):
    menu["queso"].activa = False
    menu["queso"].save()

    respuesta = validar(
        menu["sede"], **linea_base(menu, adiciones=[{"adicion": menu["queso"].id, "cantidad": 1}])
    )

    assert respuesta.status_code == 400


def test_producto_con_tamanos_exige_elegir_uno(menu):
    respuesta = validar(menu["sede"], producto=menu["producto"].id, cantidad=1)

    assert respuesta.status_code == 400
    assert "tamano" in respuesta.data


def test_tamano_inactivo_o_de_otro_producto(menu):
    menu["doble"].activo = False
    menu["doble"].save()
    otro = Producto.objects.create(
        categoria=menu["categoria"], nombre="Perro", precio_base=Decimal("15000"),
        tiempo_preparacion=10,
    )
    ajeno = ProductoTamano.objects.create(producto=otro, nombre="Grande")

    inactivo = validar(menu["sede"], **linea_base(menu, tamano=menu["doble"].id))
    de_otro = validar(menu["sede"], **linea_base(menu, tamano=ajeno.id))

    assert inactivo.status_code == 400
    assert de_otro.status_code == 400


def test_producto_sin_tamanos_no_lo_exige(menu):
    ProductoTamano.objects.filter(producto=menu["producto"]).update(activo=False)

    respuesta = validar(menu["sede"], producto=menu["producto"].id, cantidad=1)

    assert respuesta.status_code == 200
    assert respuesta.data["precio_unitario"] == "20000.00"


def test_cantidad_cero_no_se_acepta(menu):
    respuesta = validar(menu["sede"], **linea_base(menu, cantidad=0))

    assert respuesta.status_code == 400
    assert "cantidad" in respuesta.data


def test_cantidad_no_supera_el_stock_cuando_se_controla_por_unidades(menu):
    producto = menu["producto"]
    producto.tipo_control_stock = Producto.TipoControlStock.PRODUCTO
    producto.save()
    InventarioProducto.objects.filter(producto=producto).update(stock_actual=3)

    en_el_limite = validar(menu["sede"], **linea_base(menu, cantidad=3))
    excedida = validar(menu["sede"], **linea_base(menu, cantidad=4))

    assert en_el_limite.status_code == 200
    assert excedida.status_code == 400
    assert "Solo quedan 3" in str(excedida.data["cantidad"])


def test_control_por_insumos_aun_no_limita_la_cantidad(menu):
    """Hook: el control por insumos llega con HU-14 (Sprint 2)."""
    producto = menu["producto"]
    producto.tipo_control_stock = Producto.TipoControlStock.INSUMOS
    producto.save()

    respuesta = validar(menu["sede"], **linea_base(menu, cantidad=50))

    assert respuesta.status_code == 200


def test_producto_no_disponible_en_la_sede(menu):
    InventarioProducto.objects.filter(producto=menu["producto"]).update(disponible=False)

    respuesta = validar(menu["sede"], **linea_base(menu))

    assert respuesta.status_code == 400
    assert "no está disponible" in str(respuesta.data["producto"])


def test_sede_inexistente(menu):
    respuesta = APIClient().post(
        "/api/menu/sedes/9999/carrito/linea/", linea_base(menu), format="json"
    )

    assert respuesta.status_code == 404


def test_detalle_del_producto_no_ofrece_adiciones_eliminadas(menu):
    menu["queso"].activa = False
    menu["queso"].save()

    respuesta = APIClient().get(f"/api/menu/productos/{menu['producto'].id}/")

    assert respuesta.status_code == 200
    assert respuesta.data["adiciones"] == []


def test_detalle_del_producto_no_falla_con_un_token_vencido(menu):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION="Bearer token-vencido")

    respuesta = api.get(f"/api/menu/productos/{menu['producto'].id}/")

    assert respuesta.status_code == 200


def test_no_se_puede_quitar_un_ingrediente_y_agregar_su_adicion(menu):
    queso_base = ProductoInsumo.objects.create(
        producto=menu["producto"], insumo=menu["queso"].insumo,
        cantidad_necesaria=Decimal("30"), es_excluible=True,
    )

    respuesta = validar(
        menu["sede"],
        **linea_base(
            menu, exclusiones=[queso_base.id],
            adiciones=[{"adicion": menu["queso"].id, "cantidad": 1}],
        ),
    )

    assert respuesta.status_code == 400
    assert 'No puedes quitar "Queso" y agregar "Queso extra"' in str(respuesta.data["exclusiones"])


def test_quitar_un_ingrediente_y_agregar_otra_adicion_si_se_permite(menu):
    respuesta = validar(
        menu["sede"],
        **linea_base(
            menu, exclusiones=[menu["cebolla"].id],
            adiciones=[{"adicion": menu["queso"].id, "cantidad": 1}],
        ),
    )

    assert respuesta.status_code == 200


def test_detalle_indica_el_insumo_de_cada_adicion(menu):
    respuesta = APIClient().get(f"/api/menu/productos/{menu['producto'].id}/")

    assert respuesta.data["adiciones"][0]["insumo"] == menu["queso"].insumo_id
