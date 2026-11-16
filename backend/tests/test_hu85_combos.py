"""Pruebas de HU-85 · Gestionar combos (crear, editar y desactivar)."""
from datetime import timedelta
from decimal import Decimal

import pytest
from django.contrib.auth.models import Group
from django.utils import timezone
from rest_framework.test import APIClient

from inventario.models import InventarioInsumo, InventarioProducto
from menu.models import CategoriaMenu, Insumo, Producto, ProductoInsumo
from promociones import cupos
from promociones.models import Combo, ComboProducto, ComboSede
from sedes.models import Ciudad, Sede
from usuarios.models import Empleado, Usuario
from usuarios.roles import ADMINISTRADOR, OPERADOR, REPARTIDOR

URL = "/api/combos/"
pytestmark = pytest.mark.django_db


def _sede(nombre="Centro"):
    ciudad, _ = Ciudad.objects.get_or_create(nombre="Cali")
    return Sede.objects.create(
        ciudad=ciudad, nombre=nombre, direccion="Calle 1 # 2-3", latitud=3.45,
        longitud=-76.53, barrio="Granada", telefono="3000000000", correo="s@correo.com",
    )


def _personal(rol, email, sede):
    usuario = Usuario.objects.create_user(username=email, email=email, password="ClaveSegura2026")
    usuario.groups.add(Group.objects.get_or_create(name=rol)[0])
    Empleado.objects.create(
        usuario=usuario, sede=sede, tipo_documento="CC", num_documento=email[:10],
        nombres="N", apellidos="A", celular="3001234567", direccion="Calle 4",
    )
    return usuario


def _api(usuario=None):
    cliente = APIClient()
    if usuario is not None:
        cliente.force_authenticate(usuario)
    return cliente


@pytest.fixture
def categoria():
    return CategoriaMenu.objects.create(nombre="Platos")


def _producto(categoria, nombre, precio, control="NINGUNO"):
    return Producto.objects.create(
        categoria=categoria, nombre=nombre, precio_base=precio, tiempo_preparacion=10,
        tipo_control_stock=control,
    )


@pytest.fixture
def sede():
    return _sede()


@pytest.fixture
def operador(sede):
    return _personal(OPERADOR, "operador@correo.com", sede)


@pytest.fixture
def hamburguesa(categoria):
    return _producto(categoria, "Hamburguesa", 15000)


@pytest.fixture
def papas(categoria):
    return _producto(categoria, "Papas", 8000)


def _datos(hamburguesa, papas, **cambios):
    hoy = timezone.localdate()
    base = {
        "nombre": "Combo clásico", "descripcion": "Hamburguesa y papas",
        "precio": "20000.00", "fecha_inicio": str(hoy), "fecha_vencimiento": str(hoy + timedelta(days=30)),
        "productos": [
            {"producto": hamburguesa.pk, "cantidad": 1},
            {"producto": papas.pk, "cantidad": 1},
        ],
    }
    base.update(cambios)
    return base


def _crear(api, hamburguesa, papas, **cambios):
    return api.post(URL, _datos(hamburguesa, papas, **cambios), format="json")


# --- Criterio 1: armar combos con varios productos a un precio especial -------------


def test_el_operador_crea_un_combo_en_su_sede(operador, sede, hamburguesa, papas):
    respuesta = _crear(_api(operador), hamburguesa, papas, cupo_max_diario=10)
    assert respuesta.status_code == 201, respuesta.data
    combo = Combo.objects.get()
    assert ComboProducto.objects.filter(combo=combo).count() == 2
    enlace = ComboSede.objects.get(combo=combo)
    assert enlace.sede == sede and enlace.cupo_max_diario == 10 and enlace.activo
    datos = respuesta.data
    assert datos["suma_individual"] == "23000.00"
    assert datos["ahorro"] == "3000.00"
    assert datos["disponible"] is True and datos["motivo_no_disponible"] is None
    assert datos["cupo_max_diario"] == 10 and datos["cupo_restante"] == 10
    assert [p["nombre"] for p in datos["productos_detalle"]] == ["Hamburguesa", "Papas"]


def test_el_administrador_debe_elegir_sede(sede, hamburguesa, papas):
    admin = _personal(ADMINISTRADOR, "admin@correo.com", sede)
    api = _api(admin)
    sin_sede = _crear(api, hamburguesa, papas)
    assert sin_sede.status_code == 400 and "sede" in sin_sede.data
    otra = _sede("Norte")
    con_sede = _crear(api, hamburguesa, papas, sede=otra.pk)
    assert con_sede.status_code == 201
    assert ComboSede.objects.get().sede == otra


def test_exige_al_menos_dos_productos_sin_repetir(operador, hamburguesa, papas):
    api = _api(operador)
    uno = _crear(api, hamburguesa, papas, productos=[{"producto": hamburguesa.pk, "cantidad": 1}])
    assert uno.status_code == 400 and "productos" in uno.data
    repetido = _crear(api, hamburguesa, papas, productos=[
        {"producto": hamburguesa.pk, "cantidad": 1}, {"producto": hamburguesa.pk, "cantidad": 1},
    ])
    assert repetido.status_code == 400
    mismo_doble = _crear(api, hamburguesa, papas, precio="25000", productos=[
        {"producto": hamburguesa.pk, "cantidad": 2},
    ])
    assert mismo_doble.status_code == 201  # 2 × 15.000 = 30.000 > 25.000


def test_no_acepta_productos_desactivados(operador, hamburguesa, papas):
    papas.activo = False
    papas.save()
    respuesta = _crear(_api(operador), hamburguesa, papas)
    assert respuesta.status_code == 400 and "productos" in respuesta.data


# --- Criterio 2: el precio debe ser menor que la suma individual ---------------------


@pytest.mark.parametrize("precio", ["23000", "25000"])
def test_rechaza_precio_igual_o_mayor_que_la_suma(operador, hamburguesa, papas, precio):
    respuesta = _crear(_api(operador), hamburguesa, papas, precio=precio)
    assert respuesta.status_code == 400
    assert "menor que el total individual" in str(respuesta.data["precio"])
    assert Combo.objects.count() == 0


def test_la_suma_respeta_las_cantidades(operador, hamburguesa, papas):
    respuesta = _crear(_api(operador), hamburguesa, papas, precio="45000", productos=[
        {"producto": hamburguesa.pk, "cantidad": 2},
        {"producto": papas.pk, "cantidad": 2},
    ])
    assert respuesta.status_code == 201  # suma 46.000


def test_precio_cero_o_negativo_es_invalido(operador, hamburguesa, papas):
    for precio in ["0", "-5"]:
        assert _crear(_api(operador), hamburguesa, papas, precio=precio).status_code == 400


def test_al_editar_se_vuelve_a_validar_el_precio(operador, hamburguesa, papas):
    api = _api(operador)
    combo_id = _crear(api, hamburguesa, papas).data["id"]
    malo = api.patch(f"{URL}{combo_id}/", {"precio": "23000"}, format="json")
    assert malo.status_code == 400
    # Quitar productos también cambia la suma: con solo papas ×2 (16.000) 20.000 ya no sirve.
    sin_hamburguesa = api.patch(
        f"{URL}{combo_id}/", {"productos": [{"producto": papas.pk, "cantidad": 2}]}, format="json"
    )
    assert sin_hamburguesa.status_code == 400


# --- Criterio 3: producto agotado o desactivado → combo "No disponible" --------------


def test_si_un_producto_se_desactiva_el_combo_no_esta_disponible(operador, hamburguesa, papas):
    api = _api(operador)
    combo_id = _crear(api, hamburguesa, papas).data["id"]
    papas.activo = False
    papas.save()
    datos = api.get(f"{URL}{combo_id}/").data
    assert datos["disponible"] is False
    assert "Papas" in datos["motivo_no_disponible"] and "desactivado" in datos["motivo_no_disponible"]
    papas.activo = True
    papas.save()
    assert api.get(f"{URL}{combo_id}/").data["disponible"] is True


def test_si_un_producto_con_stock_se_agota_el_combo_no_esta_disponible(operador, sede, categoria):
    con_stock = _producto(categoria, "Pizza", 20000, control="PRODUCTO")
    bebida = _producto(categoria, "Gaseosa", 5000)
    inv = InventarioProducto.objects.create(sede=sede, producto=con_stock, stock_actual=5)
    api = _api(operador)
    respuesta = api.post(URL, {
        "nombre": "Pizza y gaseosa", "precio": "22000",
        "fecha_inicio": str(timezone.localdate()),
        "fecha_vencimiento": str(timezone.localdate() + timedelta(days=5)),
        "productos": [{"producto": con_stock.pk, "cantidad": 1}, {"producto": bebida.pk, "cantidad": 1}],
    }, format="json")
    assert respuesta.status_code == 201 and respuesta.data["disponible"] is True
    inv.stock_actual = 0
    inv.save()
    datos = api.get(f"{URL}{respuesta.data['id']}/").data
    assert datos["disponible"] is False and "agotado" in datos["motivo_no_disponible"]
    assert [p["disponible"] for p in datos["productos_detalle"]] == [False, True]


def test_producto_por_insumos_sin_existencias_agota_el_combo(operador, sede, categoria, papas):
    sopa = _producto(categoria, "Sopa", 12000, control="INSUMOS")
    insumo = Insumo.objects.create(nombre="Caldo", unidad_medida="l")
    ProductoInsumo.objects.create(producto=sopa, insumo=insumo, cantidad_necesaria=Decimal("0.5"))
    inv = InventarioInsumo.objects.create(sede=sede, insumo=insumo, stock_actual=Decimal("0.4"))
    api = _api(operador)
    respuesta = api.post(URL, {
        "nombre": "Sopa y papas", "precio": "17000",
        "fecha_inicio": str(timezone.localdate()),
        "fecha_vencimiento": str(timezone.localdate() + timedelta(days=5)),
        "productos": [{"producto": sopa.pk, "cantidad": 1}, {"producto": papas.pk, "cantidad": 1}],
    }, format="json")
    assert respuesta.data["disponible"] is False
    inv.stock_actual = Decimal("1.0")
    inv.save()
    assert api.get(f"{URL}{respuesta.data['id']}/").data["disponible"] is True


def test_combo_vencido_o_desactivado_no_esta_disponible(operador, hamburguesa, papas):
    api = _api(operador)
    combo_id = _crear(api, hamburguesa, papas).data["id"]
    Combo.objects.filter(pk=combo_id).update(fecha_vencimiento=timezone.localdate() - timedelta(days=1),
                                             fecha_inicio=timezone.localdate() - timedelta(days=9))
    assert api.get(f"{URL}{combo_id}/").data["disponible"] is False


# --- Criterio 4: modificar aplica a futuro; desactivar conserva el historial ---------


def test_editar_cambia_precio_y_productos(operador, hamburguesa, papas, categoria):
    api = _api(operador)
    combo_id = _crear(api, hamburguesa, papas).data["id"]
    jugo = _producto(categoria, "Jugo", 6000)
    respuesta = api.patch(f"{URL}{combo_id}/", {
        "precio": "21000", "cupo_max_diario": 5,
        "productos": [
            {"producto": hamburguesa.pk, "cantidad": 1},
            {"producto": papas.pk, "cantidad": 1},
            {"producto": jugo.pk, "cantidad": 1},
        ],
    }, format="json")
    assert respuesta.status_code == 200, respuesta.data
    assert ComboProducto.objects.filter(combo_id=combo_id).count() == 3
    assert respuesta.data["precio"] == "21000.00" and respuesta.data["cupo_max_diario"] == 5
    assert ComboSede.objects.get(combo_id=combo_id).cupo_max_diario == 5


def test_quitar_el_cupo_editando(operador, hamburguesa, papas):
    api = _api(operador)
    combo_id = _crear(api, hamburguesa, papas, cupo_max_diario=3).data["id"]
    respuesta = api.patch(f"{URL}{combo_id}/", {"cupo_max_diario": None}, format="json")
    assert respuesta.status_code == 200 and respuesta.data["cupo_max_diario"] is None
    assert ComboSede.objects.get().cupo_max_diario is None


def test_delete_desactiva_y_se_puede_reactivar(operador, hamburguesa, papas):
    api = _api(operador)
    combo_id = _crear(api, hamburguesa, papas).data["id"]
    assert api.delete(f"{URL}{combo_id}/").status_code == 204
    combo = Combo.objects.get(pk=combo_id)  # sigue existiendo: el historial se conserva
    assert combo.activo is False and ComboSede.objects.get(combo=combo).activo is False
    assert api.get(f"{URL}{combo_id}/").data["disponible"] is False
    api.patch(f"{URL}{combo_id}/", {"activo": True}, format="json")
    assert api.get(f"{URL}{combo_id}/").data["disponible"] is True


# --- Cupo diario (HU-64) -------------------------------------------------------------


def test_el_cupo_del_combo_se_ve_en_la_api(operador, sede, hamburguesa, papas):
    from pedidos.models import Pedido

    api = _api(operador)
    combo_id = _crear(api, hamburguesa, papas, cupo_max_diario=3).data["id"]
    enlace = ComboSede.objects.get(combo_id=combo_id)
    cupos.consumir(enlace, Pedido.objects.create(numero_pedido="P-T-1", sede=sede), cantidad=2)
    datos = api.get(f"{URL}{combo_id}/").data
    assert datos["usos_hoy"] == 2 and datos["cupo_restante"] == 1
    assert api.patch(f"{URL}{combo_id}/", {"cupo_max_diario": 0}, format="json").status_code == 400


# --- Sede y permisos --------------------------------------------------------------------


def test_nombre_unico_por_sede_sin_distinguir_mayusculas(operador, hamburguesa, papas):
    api = _api(operador)
    assert _crear(api, hamburguesa, papas).status_code == 201
    repetido = _crear(api, hamburguesa, papas, nombre="COMBO CLÁSICO".replace("Á", "á"))
    assert repetido.status_code == 400 and "nombre" in repetido.data


def test_el_operador_solo_ve_y_edita_los_de_su_sede(operador, hamburguesa, papas):
    otra = _sede("Norte")
    admin = _personal(ADMINISTRADOR, "admin@correo.com", otra)
    ajeno = _crear(_api(admin), hamburguesa, papas, sede=otra.pk).data["id"]
    propio = _crear(_api(operador), hamburguesa, papas, nombre="Mío").data["id"]
    api = _api(operador)
    assert [c["id"] for c in api.get(URL).data] == [propio]
    assert api.get(f"{URL}{ajeno}/").status_code == 404
    assert api.patch(f"{URL}{ajeno}/", {"precio": "1000"}, format="json").status_code == 404
    assert api.delete(f"{URL}{ajeno}/").status_code == 404
    assert {c["id"] for c in _api(admin).get(URL).data} == {propio, ajeno}
    assert [c["id"] for c in _api(admin).get(URL, {"sede": otra.pk}).data] == [ajeno]


def test_no_se_mueve_un_combo_de_sede(operador, hamburguesa, papas):
    otra = _sede("Norte")
    api = _api(operador)
    combo_id = _crear(api, hamburguesa, papas).data["id"]
    assert api.patch(f"{URL}{combo_id}/", {"sede": otra.pk}, format="json").status_code == 400


def test_otros_roles_y_anonimos_no_entran(sede):
    assert _api().get(URL).status_code == 401
    repartidor = _personal(REPARTIDOR, "rep@correo.com", sede)
    assert _api(repartidor).get(URL).status_code == 403


def test_fechas_invalidas(operador, hamburguesa, papas):
    hoy = timezone.localdate()
    respuesta = _crear(_api(operador), hamburguesa, papas,
                       fecha_inicio=str(hoy), fecha_vencimiento=str(hoy - timedelta(days=1)))
    assert respuesta.status_code == 400 and "fecha_vencimiento" in respuesta.data


def test_producto_sin_control_desactivado_en_la_sede_tumba_el_combo(operador, sede, hamburguesa, papas):
    api = _api(operador)
    combo_id = _crear(api, hamburguesa, papas).data["id"]
    inv = InventarioProducto.objects.create(sede=sede, producto=papas, stock_actual=0, disponible=False)
    datos = api.get(f"{URL}{combo_id}/").data
    assert datos["disponible"] is False and "no está disponible" in datos["motivo_no_disponible"]
    inv.disponible, inv.stock_actual = True, 5
    inv.save()
    assert api.get(f"{URL}{combo_id}/").data["disponible"] is True


def test_producto_sin_control_con_stock_cero_en_inventario_tumba_el_combo(operador, sede, hamburguesa, papas):
    api = _api(operador)
    combo_id = _crear(api, hamburguesa, papas).data["id"]
    inv = InventarioProducto.objects.create(sede=sede, producto=hamburguesa, stock_actual=0)
    datos = api.get(f"{URL}{combo_id}/").data
    assert datos["disponible"] is False and "agotado" in datos["motivo_no_disponible"]
    inv.stock_actual = 3
    inv.save()
    assert api.get(f"{URL}{combo_id}/").data["disponible"] is True