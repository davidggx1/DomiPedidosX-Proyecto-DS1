from datetime import date, time
from decimal import Decimal
from types import SimpleNamespace

import pytest
from rest_framework.test import APIClient

from menu.models import CategoriaMenu, Producto
from pedidos.models import EstadoPedido, Pedido
from sedes.models import CapacidadSede, Ciudad, Sede, ZonaCobertura
from usuarios.models import Cliente, DireccionEntrega, Usuario

ESTIMAR_URL = "/api/pedidos/estimar-tiempo/"
CONFIRMAR_URL = "/api/pedidos/confirmar/"
pytestmark = pytest.mark.django_db


@pytest.fixture
def escenario(db):
    ciudad = Ciudad.objects.create(nombre="Cali")
    sede = Sede.objects.create(
        ciudad=ciudad, nombre="Sede Norte", direccion="Calle 10 # 5-20",
        latitud=3.45, longitud=-76.53, barrio="Versalles",
        telefono="3001112233", correo="norte@correo.com",
    )
    CapacidadSede.objects.create(
        sede=sede,
        hora_inicio=time(0, 0),
        hora_fin=time(23, 59),
        dias_semana="lunes,martes,miercoles,jueves,viernes,sabado,domingo",
        max_pedidos_simultaneos=10,
        umbral_alerta=5,
    )
    zona_cerca = ZonaCobertura.objects.create(
        sede=sede, nombre="Zona Cercana", radio=2, centro_latitud=3.45, centro_longitud=-76.53,
        tarifa_domicilio=Decimal("3000"), tiempo_estimado=20, pedido_minimo=Decimal("10000"),
    )
    zona_lejos = ZonaCobertura.objects.create(
        sede=sede, nombre="Zona Lejana", radio=2, centro_latitud=3.50, centro_longitud=-76.53,
        tarifa_domicilio=Decimal("6000"), tiempo_estimado=40, pedido_minimo=Decimal("10000"),
    )
    usuario = Usuario.objects.create_user(
        username="cliente_hu48@correo.com", email="cliente_hu48@correo.com", password="ClaveSegura2026"
    )
    cliente = Cliente.objects.create(
        usuario=usuario, tipo_documento="CC", num_documento="987654",
        nombres="Carlos", apellidos="Gomez", celular="3009998877", fecha_nacimiento=date(1998, 5, 10),
    )
    dir_cerca = DireccionEntrega.objects.create(
        ciudad=ciudad, cliente=cliente, direccion="Calle 11 # 5-10", latitud=3.451, longitud=-76.53
    )
    dir_lejos = DireccionEntrega.objects.create(
        ciudad=ciudad, cliente=cliente, direccion="Calle 70 # 2-15", latitud=3.501, longitud=-76.53
    )
    cat = CategoriaMenu.objects.create(nombre="Hamburguesas")
    prod = Producto.objects.create(
        categoria=cat, nombre="Doble Carne", precio_base=Decimal("25000"), tiempo_preparacion=15,
    )
    api = APIClient()
    api.force_authenticate(user=usuario)
    return SimpleNamespace(
        api=api, sede=sede, zona_cerca=zona_cerca, zona_lejos=zona_lejos,
        dir_cerca=dir_cerca, dir_lejos=dir_lejos, prod=prod,
    )


def test_rango_estimado_en_confirmacion_y_seguimiento(escenario):
    resp = escenario.api.post(
        CONFIRMAR_URL,
        {
            "sede_id": escenario.sede.pk,
            "direccion_id": escenario.dir_cerca.pk,
            "metodo_pago": "tarjeta",
            "items": [{"producto_id": escenario.prod.pk, "cantidad": 1}],
        },
        format="json",
    )
    assert resp.status_code == 201
    # 20 (zona) + 15 (prep) + 0 (cola) = 35 -> rango "35-45 min"
    assert resp.data["tiempo_estimado_entrega"] == 35
    assert resp.data["tiempo_estimado_rango"] == "35-45 min"

    tracking = escenario.api.get(f"/api/pedidos/{resp.data['id']}/estado/")
    assert tracking.status_code == 200
    assert tracking.data["tiempo_estimado_rango"] == "35-45 min"


def test_zonas_distintas_con_mismos_productos_dan_tiempos_diferentes(escenario):
    items = [{"producto_id": escenario.prod.pk, "cantidad": 1}]
    r_cerca = escenario.api.post(
        ESTIMAR_URL,
        {"sede_id": escenario.sede.pk, "direccion_id": escenario.dir_cerca.pk, "items": items},
        format="json",
    )
    r_lejos = escenario.api.post(
        ESTIMAR_URL,
        {"sede_id": escenario.sede.pk, "direccion_id": escenario.dir_lejos.pk, "items": items},
        format="json",
    )
    assert r_cerca.status_code == 200 and r_lejos.status_code == 200
    assert r_cerca.data["tiempo_estimado_min"] < r_lejos.data["tiempo_estimado_min"]
    assert r_lejos.data["tiempo_estimado_min"] - r_cerca.data["tiempo_estimado_min"] == 20


def test_congestion_cocina_aumenta_tiempo_estimado(escenario):
    items = [{"producto_id": escenario.prod.pk, "cantidad": 1}]
    payload = {"sede_id": escenario.sede.pk, "direccion_id": escenario.dir_cerca.pk, "items": items}

    sin_carga = escenario.api.post(ESTIMAR_URL, payload, format="json").data["tiempo_estimado_min"]

    for i in range(5):
        Pedido.objects.create(
            numero_pedido=f"P-TEST-{i:04d}",
            sede=escenario.sede,
            estado=EstadoPedido.EN_PREPARACION,
        )

    con_carga = escenario.api.post(ESTIMAR_URL, payload, format="json").data["tiempo_estimado_min"]
    assert con_carga > sin_carga