from decimal import Decimal

import pytest
from django.contrib.auth.models import Group
from rest_framework.test import APIClient

from pedidos.models import Factura, Pedido
from sedes.geometria import contiene_punto, normalizar_poligono, traslapan
from sedes.models import Ciudad, Sede, ZonaCobertura
from usuarios.models import Usuario

URL = "/api/zonas-cobertura/"
pytestmark = pytest.mark.django_db

CUADRADO = [[3.44, -76.54], [3.44, -76.52], [3.46, -76.52], [3.46, -76.54]]
CUADRADO_LEJOS = [[3.64, -76.54], [3.64, -76.52], [3.66, -76.52], [3.66, -76.54]]


def _sede(nombre="Norte"):
    ciudad, _ = Ciudad.objects.get_or_create(nombre="Cali")
    return Sede.objects.create(
        ciudad=ciudad, nombre=nombre, direccion="Calle 1 # 2-3", latitud=3.45,
        longitud=-76.53, barrio="Granada", telefono="3000000000", correo="s@correo.com",
    )


def _usuario(email, rol=None):
    usuario = Usuario.objects.create_user(username=email, email=email, password="ClaveSegura2026")
    if rol:
        usuario.groups.add(Group.objects.get_or_create(name=rol)[0])
    return usuario


def _http(usuario=None):
    c = APIClient()
    if usuario:
        c.force_authenticate(user=usuario)
    return c


@pytest.fixture
def admin():
    return _http(_usuario("admin@correo.com", "administrador"))


@pytest.fixture
def sede():
    return _sede()


def _extra():
    return {"tarifa_domicilio": "3000", "tiempo_estimado": 40, "pedido_minimo": "10000"}


def _radio(sede, nombre="Zona A", lat=3.45, lon=-76.53, radio=2, **extra):
    return {
        "sede": sede.pk, "nombre": nombre, "radio": radio,
        "centro_latitud": lat, "centro_longitud": lon, **_extra(), **extra,
    }


def _poligono(sede, vertices=CUADRADO, nombre="Zona P", **extra):
    return {
        "sede": sede.pk, "nombre": nombre, "poligono_vertices": vertices, **_extra(), **extra,
    }


def _zona(sede, nombre="Zona A", lat=3.45, lon=-76.53, radio=2, **extra):
    return ZonaCobertura.objects.create(
        sede=sede, nombre=nombre, radio=radio, centro_latitud=lat, centro_longitud=lon,
        tarifa_domicilio=Decimal("3000"), tiempo_estimado=40, pedido_minimo=Decimal("10000"),
        **extra,
    )


def test_crear_zona_por_radio(admin, sede):
    r = admin.post(URL, _radio(sede), format="json")
    assert r.status_code == 201
    assert r.data["tipo"] == "radio"


def test_radio_cero_es_rechazado(admin, sede):
    r = admin.post(URL, _radio(sede, radio=0), format="json")
    assert r.status_code == 400
    assert "radio" in r.data
    assert not ZonaCobertura.objects.exists()


def test_zona_por_radio_sin_datos_es_rechazada(admin, sede):
    r = admin.post(URL, {"sede": sede.pk, "nombre": "X", **_extra()}, format="json")
    assert r.status_code == 400
    assert "radio" in r.data


def test_crear_zona_por_poligono_calcula_centro_y_radio(admin, sede):
    r = admin.post(URL, _poligono(sede), format="json")
    assert r.status_code == 201
    assert r.data["tipo"] == "poligono"
    assert r.data["radio"] > 0
    assert abs(r.data["centro_latitud"] - 3.45) < 0.001


def test_poligono_cerrado_repitiendo_el_primer_punto_se_normaliza(admin, sede):
    cerrado = CUADRADO + [CUADRADO[0]]
    r = admin.post(URL, _poligono(sede, cerrado), format="json")
    assert r.status_code == 201
    assert len(r.data["poligono_vertices"]) == 4


@pytest.mark.parametrize("vertices", [[[3.44, -76.54], [3.44, -76.52]], [], "no-es-lista"])
def test_poligono_abierto_o_incompleto_es_rechazado(admin, sede, vertices):
    r = admin.post(URL, _poligono(sede, vertices), format="json")
    assert r.status_code == 400
    assert not ZonaCobertura.objects.exists()


def test_poligono_que_se_cruza_a_si_mismo_es_rechazado(admin, sede):
    corbata = [[3.44, -76.54], [3.46, -76.52], [3.46, -76.54], [3.44, -76.52]]
    r = admin.post(URL, _poligono(sede, corbata), format="json")
    assert r.status_code == 400
    assert "poligono_vertices" in r.data


def test_radios_que_se_traslapan_en_la_misma_sede(admin, sede):
    _zona(sede)
    r = admin.post(URL, _radio(sede, "Zona B", lat=3.46), format="json")  # a ~1,1 km
    assert r.status_code == 400
    assert "traslapa" in str(r.data)


def test_mismas_coordenadas_en_otra_sede_si_se_permiten(admin, sede):
    _zona(sede)
    r = admin.post(URL, _radio(_sede("Sur")), format="json")
    assert r.status_code == 201


def test_zonas_separadas_en_la_misma_sede_si_se_permiten(admin, sede):
    _zona(sede)
    r = admin.post(URL, _radio(sede, "Zona B", lat=3.60), format="json")
    assert r.status_code == 201


def test_poligono_que_contiene_a_un_radio_se_traslapa(admin, sede):
    _zona(sede, radio=0.5)
    r = admin.post(URL, _poligono(sede), format="json")
    assert r.status_code == 400


def test_poligonos_que_se_traslapan(admin, sede):
    admin.post(URL, _poligono(sede), format="json")
    desplazado = [[la + 0.01, lo] for la, lo in CUADRADO]
    r = admin.post(URL, _poligono(sede, desplazado, "Zona Q"), format="json")
    assert r.status_code == 400


def test_poligonos_separados_si_se_permiten(admin, sede):
    admin.post(URL, _poligono(sede), format="json")
    r = admin.post(URL, _poligono(sede, CUADRADO_LEJOS, "Zona Q"), format="json")
    assert r.status_code == 201


def test_zona_inactiva_no_bloquea_pero_al_reactivarla_se_valida(admin, sede):
    _zona(sede, activo=False)
    r = admin.post(URL, _radio(sede, "Zona B"), format="json")  # mismo lugar, la otra está inactiva
    assert r.status_code == 201
    inactiva = ZonaCobertura.objects.get(nombre="Zona A")
    r = admin.patch(f"{URL}{inactiva.pk}/", {"activo": True}, format="json")
    assert r.status_code == 400


def test_editar_una_zona_no_choca_consigo_misma(admin, sede):
    zona = _zona(sede)
    r = admin.patch(f"{URL}{zona.pk}/", {"nombre": "Renombrada", "radio": 2.5}, format="json")
    assert r.status_code == 200
    zona.refresh_from_db()
    assert zona.nombre == "Renombrada" and zona.radio == 2.5


def test_no_se_puede_mover_una_zona_a_otra_sede(admin, sede):
    zona = _zona(sede)
    r = admin.patch(f"{URL}{zona.pk}/", {"sede": _sede("Sur").pk}, format="json")
    assert r.status_code == 400


def test_tarifa_negativa_es_rechazada(admin, sede):
    r = admin.post(URL, _radio(sede, tarifa_domicilio="-1"), format="json")
    assert r.status_code == 400
    assert "tarifa_domicilio" in r.data


def test_filtros_por_sede_y_activo(admin, sede):
    _zona(sede)
    _zona(sede, "Zona B", lat=3.60, activo=False)
    _zona(_sede("Sur"), "Zona C")
    assert len(admin.get(f"{URL}?sede={sede.pk}").data) == 2
    assert len(admin.get(f"{URL}?sede={sede.pk}&activo=true").data) == 1


def test_solo_el_administrador_gestiona_zonas(sede):
    cliente = _http(_usuario("c@correo.com"))
    operador = _http(_usuario("op@correo.com", "operador"))
    assert cliente.get(URL).status_code == 403
    assert operador.post(URL, _radio(sede), format="json").status_code == 403
    assert _http().get(URL).status_code == 401


def test_cambios_no_alteran_pedidos_anteriores(admin, sede):
    zona = _zona(sede)
    pedido = Pedido.objects.create(
        numero_pedido="P-1", sede=sede, zona_cobertura=zona, tiempo_estimado_entrega=40
    )
    Factura.objects.create(
        pedido=pedido, numero="F-1", subtotal=10000, iva=0, costo_domicilio=3000,
        total=13000, metodo_pago="tarjeta",
    )
    r = admin.patch(
        f"{URL}{zona.pk}/", {"tarifa_domicilio": "5000", "tiempo_estimado": 60}, format="json"
    )
    assert r.status_code == 200
    pedido.refresh_from_db()
    assert pedido.tiempo_estimado_entrega == 40
    assert pedido.factura.costo_domicilio == Decimal("3000")


def test_zona_con_pedidos_no_se_elimina_pero_sin_pedidos_si(admin, sede):
    con_pedidos, libre = _zona(sede), _zona(sede, "Zona B", lat=3.60)
    Pedido.objects.create(numero_pedido="P-1", sede=sede, zona_cobertura=con_pedidos)
    assert admin.delete(f"{URL}{con_pedidos.pk}/").status_code == 409
    assert ZonaCobertura.objects.filter(pk=con_pedidos.pk).exists()
    assert admin.delete(f"{URL}{libre.pk}/").status_code == 204


# --- Geometría pura -------------------------------------------------------

def test_traslape_entre_circulos_tangentes_no_cuenta():
    a = (3.45, -76.53, 1.0, None)
    lejos = (3.45, -76.53 + 0.05, 1.0, None)  # ~5,5 km entre centros
    assert not traslapan(a, lejos)
    assert traslapan(a, (3.45, -76.53 + 0.01, 1.0, None))


def test_contiene_punto_en_poligono_y_en_radio():
    assert contiene_punto(3.45, -76.53, 3.45, -76.53, 1.0, CUADRADO)
    assert not contiene_punto(3.50, -76.53, 3.45, -76.53, 4.0, CUADRADO)
    assert contiene_punto(3.46, -76.53, 3.45, -76.53, 2.0, None)
    assert not contiene_punto(3.60, -76.53, 3.45, -76.53, 2.0, None)


def test_normalizar_poligono_rechaza_coordenadas_fuera_de_rango():
    with pytest.raises(ValueError):
        normalizar_poligono([[95, 0], [0, 1], [1, 1]])