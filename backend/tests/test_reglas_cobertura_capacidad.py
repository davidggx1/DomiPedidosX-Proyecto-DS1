"""
SCRUM-121 · Pruebas de reglas de negocio: polígonos de cobertura y franjas de capacidad.

Complementa las pruebas por historia (HU-55, HU-58, HU-59, HU-61) con casos borde:

1. Geometría pura (sedes/geometria.py): polígonos cóncavos, bordes, orientación,
   puntos repetidos, polígonos degenerados y traslapes que solo se tocan.
2. Cobertura (HU-58): el endpoint que consulta el cliente antes de pagar debe dar
   la misma respuesta que la validación al confirmar el pedido.
3. Franjas de capacidad (HU-59): solapes por día y hora, franjas contiguas, el
   cambio de franja justo en el borde y la validación de los días de la semana.
"""
import datetime as dt
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest
from django.contrib.auth.models import Group
from rest_framework.test import APIClient

from pedidos.capacidad import franja_actual
from sedes.geometria import (
    MAX_VERTICES,
    contiene_punto,
    distancia_km,
    normalizar_poligono,
    traslapan,
)
from sedes.models import CapacidadSede, Ciudad, Sede, ZonaCobertura
from usuarios.models import Usuario
from usuarios.roles import ADMINISTRADOR

TZ = ZoneInfo("America/Bogota")
LUNES = dt.date(2026, 11, 9)
MIERCOLES = dt.date(2026, 11, 11)

# Polígono en forma de "L" alrededor de (3.45, -76.53): el hueco de la L
# (esquina superior derecha) queda FUERA aunque esté dentro del rectángulo envolvente.
#
#   (3.47,-76.55) +----+ (3.47,-76.53)
#                 |    |
#                 |    +--------+ (3.45,-76.51)
#                 |             |
#   (3.43,-76.55) +-------------+ (3.43,-76.51)
L_FORMA = [
    [3.43, -76.55], [3.43, -76.51], [3.45, -76.51],
    [3.45, -76.53], [3.47, -76.53], [3.47, -76.55],
]
DENTRO_DE_LA_L = (3.44, -76.52)  # brazo inferior
HUECO_DE_LA_L = (3.46, -76.52)  # esquina recortada

CUADRADO = [[3.44, -76.54], [3.44, -76.52], [3.46, -76.52], [3.46, -76.54]]


def radio(lat, lon, km):
    return (lat, lon, km, None)


def poligono(vertices):
    lat = sum(v[0] for v in vertices) / len(vertices)
    lon = sum(v[1] for v in vertices) / len(vertices)
    return (lat, lon, 0, vertices)


# =============================================================================
# 1. Geometría pura (sin base de datos)
# =============================================================================


class TestDistancia:
    def test_un_grado_de_latitud_son_unos_111_km(self):
        assert distancia_km(3.0, -76.0, 4.0, -76.0) == pytest.approx(111.19, abs=0.05)

    def test_es_simetrica_y_cero_en_el_mismo_punto(self):
        assert distancia_km(3.45, -76.53, 3.40, -76.50) == pytest.approx(
            distancia_km(3.40, -76.50, 3.45, -76.53)
        )
        assert distancia_km(3.45, -76.53, 3.45, -76.53) == 0


class TestPuntoEnPoligono:
    def test_poligono_concavo_excluye_el_hueco(self):
        assert contiene_punto(*DENTRO_DE_LA_L, 0, 0, 0, L_FORMA)
        assert not contiene_punto(*HUECO_DE_LA_L, 0, 0, 0, L_FORMA)

    def test_el_borde_y_los_vertices_cuentan_como_dentro(self):
        assert contiene_punto(3.44, -76.53, 0, 0, 0, CUADRADO)  # sobre un lado
        assert contiene_punto(3.44, -76.54, 0, 0, 0, CUADRADO)  # sobre un vértice

    def test_no_importa_el_sentido_de_los_vertices(self):
        horario = list(reversed(L_FORMA))
        for punto in (DENTRO_DE_LA_L, HUECO_DE_LA_L, (3.50, -76.60)):
            assert contiene_punto(*punto, 0, 0, 0, L_FORMA) == contiene_punto(
                *punto, 0, 0, 0, horario
            )

    def test_radio_incluye_el_centro_y_excluye_lo_lejano(self):
        assert contiene_punto(3.45, -76.53, 3.45, -76.53, 1.0)
        assert contiene_punto(3.4545, -76.53, 3.45, -76.53, 1.0)  # ~0.5 km
        assert not contiene_punto(3.4600, -76.53, 3.45, -76.53, 1.0)  # ~1.1 km


class TestNormalizarPoligono:
    def test_quita_puntos_repetidos_seguidos_y_el_cierre(self):
        repetidos = [CUADRADO[0], CUADRADO[0], *CUADRADO[1:], CUADRADO[0]]
        assert normalizar_poligono(repetidos) == CUADRADO

    def test_puntos_alineados_no_encierran_area(self):
        with pytest.raises(ValueError, match="área"):
            normalizar_poligono([[3.44, -76.54], [3.45, -76.53], [3.46, -76.52]])

    def test_dos_puntos_distintos_no_bastan(self):
        with pytest.raises(ValueError, match="3 puntos"):
            normalizar_poligono([[3.44, -76.54], [3.46, -76.52], [3.44, -76.54]])

    def test_poligono_en_forma_de_moño_se_rechaza(self):
        moño = [[3.44, -76.54], [3.46, -76.52], [3.44, -76.52], [3.46, -76.54]]
        with pytest.raises(ValueError, match="cruza"):
            normalizar_poligono(moño)

    def test_limite_de_vertices(self):
        with pytest.raises(ValueError, match=str(MAX_VERTICES)):
            normalizar_poligono([[3.44, -76.54]] * (MAX_VERTICES + 1))

    @pytest.mark.parametrize(
        "punto",
        [[True, -76.53], ["3.44", -76.53], [3.44], [3.44, -76.53, 0], None],
        ids=["booleano", "texto", "incompleto", "sobrante", "nulo"],
    )
    def test_cada_punto_debe_ser_un_par_numerico(self, punto):
        with pytest.raises(ValueError):
            normalizar_poligono([punto, *CUADRADO])


class TestTraslape:
    def test_poligonos_que_comparten_un_lado_no_se_traslapan(self):
        vecino = [[3.44, -76.52], [3.44, -76.50], [3.46, -76.50], [3.46, -76.52]]
        assert not traslapan(poligono(CUADRADO), poligono(vecino))

    def test_poligono_dentro_de_otro_si_se_traslapa(self):
        pequeño = [[3.445, -76.535], [3.445, -76.525], [3.455, -76.525], [3.455, -76.535]]
        assert traslapan(poligono(CUADRADO), poligono(pequeño))
        assert traslapan(poligono(pequeño), poligono(CUADRADO))

    def test_radio_en_el_hueco_de_un_poligono_concavo_no_se_traslapa(self):
        # Círculo pequeño metido en la esquina recortada de la L
        assert not traslapan(poligono(L_FORMA), radio(*HUECO_DE_LA_L, 0.3))

    def test_radio_que_entra_en_el_brazo_de_la_l_si_se_traslapa(self):
        assert traslapan(poligono(L_FORMA), radio(*DENTRO_DE_LA_L, 0.3))


# =============================================================================
# Datos para las pruebas con base de datos
# =============================================================================


def _sede(nombre="Centro", lat=3.45, lon=-76.53):
    ciudad, _ = Ciudad.objects.get_or_create(nombre="Cali")
    return Sede.objects.create(
        ciudad=ciudad, nombre=nombre, direccion="Calle 1 # 2-3", latitud=lat, longitud=lon,
        barrio="Centro", telefono="3000000000", correo=f"{nombre.lower()}@correo.com",
    )


def _zona(sede, nombre="Zona", radio_km=1.0, lat=None, lon=None, vertices=None, **extra):
    datos = {
        "tarifa_domicilio": Decimal("4000"), "tiempo_estimado": 30,
        "pedido_minimo": Decimal("0"), "activo": True, **extra,
    }
    return ZonaCobertura.objects.create(
        sede=sede, nombre=nombre, radio=radio_km,
        centro_latitud=sede.latitud if lat is None else lat,
        centro_longitud=sede.longitud if lon is None else lon,
        poligono_vertices=vertices, **datos,
    )


def _admin():
    usuario = Usuario.objects.create_user(
        username="admin@correo.com", email="admin@correo.com", password="ClaveSegura2026"
    )
    usuario.groups.add(Group.objects.get_or_create(name=ADMINISTRADOR)[0])
    api = APIClient()
    api.force_authenticate(usuario)
    return api


def validar_cobertura(lat, lon):
    return APIClient().post(
        "/api/sedes/validar-cobertura/", {"latitud": lat, "longitud": lon}, format="json"
    ).data


def cubierto_al_confirmar(lat, lon):
    """La misma regla que usa confirmar el pedido (pedidos/servicios.py)."""
    return any(
        contiene_punto(lat, lon, z.centro_latitud, z.centro_longitud, z.radio, z.poligono_vertices)
        for z in ZonaCobertura.objects.filter(activo=True, sede__activa=True)
    )


# =============================================================================
# 2. Cobertura (HU-58): validar antes de pagar = validar al confirmar
# =============================================================================


@pytest.mark.django_db
class TestCoberturaConsistente:
    def test_fuera_de_la_zona_aunque_cerca_de_la_sede_no_hay_cobertura(self):
        # Zona de 1 km; el cliente está a ~3 km de la sede (antes contaba un respaldo de 5 km)
        _zona(_sede(), radio_km=1.0)

        respuesta = validar_cobertura(3.477, -76.53)

        assert respuesta["cubierto"] is False
        assert cubierto_al_confirmar(3.477, -76.53) is False

    def test_sede_sin_zonas_no_da_cobertura(self):
        _sede()

        assert validar_cobertura(3.45, -76.53)["cubierto"] is False

    def test_zona_inactiva_no_da_cobertura(self):
        _zona(_sede(), activo=False)

        assert validar_cobertura(3.45, -76.53)["cubierto"] is False

    def test_hueco_de_un_poligono_concavo_no_tiene_cobertura(self):
        _zona(_sede(), vertices=L_FORMA)

        assert validar_cobertura(*DENTRO_DE_LA_L)["cubierto"] is True
        assert validar_cobertura(*HUECO_DE_LA_L)["cubierto"] is False

    def test_con_cobertura_devuelve_la_tarifa_y_el_minimo_de_la_zona(self):
        _zona(
            _sede(), radio_km=2.0, tarifa_domicilio=Decimal("4500"), tiempo_estimado=35,
            pedido_minimo=Decimal("15000"),
        )

        sede = validar_cobertura(3.45, -76.53)["sede"]

        assert sede["tarifa_domicilio"] == 4500
        assert sede["pedido_minimo"] == 15000  # HU-57: el carrito lo usa para avisar cuánto falta
        assert sede["tiempo_estimado"] == 35

    @pytest.mark.parametrize(
        "lat,lon",
        [
            (3.45, -76.53), (3.44, -76.52), (3.46, -76.52), (3.47, -76.55),
            (3.477, -76.53), (3.43, -76.51), (3.42, -76.56), (3.50, -76.53),
        ],
    )
    def test_misma_respuesta_que_al_confirmar(self, lat, lon):
        centro = _sede("Centro")
        _zona(centro, "L", vertices=L_FORMA)
        norte = _sede("Norte", lat=3.49, lon=-76.53)
        _zona(norte, "Norte", radio_km=1.5)

        assert validar_cobertura(lat, lon)["cubierto"] == cubierto_al_confirmar(lat, lon)


# =============================================================================
# 3. Franjas de capacidad (HU-59)
# =============================================================================


def _franja(sede, inicio, fin, dias="lunes", maximo=5):
    return CapacidadSede.objects.create(
        sede=sede, hora_inicio=inicio, hora_fin=fin, dias_semana=dias,
        max_pedidos_simultaneos=maximo, umbral_alerta=max(1, maximo - 1),
    )


def _payload(sede, inicio, fin, dias="lunes", maximo=5):
    return {
        "sede": sede.pk, "hora_inicio": inicio, "hora_fin": fin, "dias_semana": dias,
        "max_pedidos_simultaneos": maximo, "umbral_alerta": max(1, maximo - 1),
    }


def _a_las(fecha, hora, minuto=0, segundo=0):
    return dt.datetime.combine(fecha, dt.time(hora, minuto, segundo), tzinfo=TZ)


@pytest.mark.django_db
class TestSolapeDeFranjas:
    URL = "/api/capacidades/"

    @pytest.mark.parametrize(
        "inicio,fin",
        [("12:00", "13:00"), ("10:00", "12:00"), ("13:00", "16:00"), ("10:00", "16:00")],
        ids=["contenida", "cruza-el-inicio", "cruza-el-fin", "la-contiene"],
    )
    def test_franjas_que_se_cruzan_el_mismo_dia_se_rechazan(self, inicio, fin):
        sede = _sede()
        _franja(sede, "11:00", "14:00", "lunes,martes")

        respuesta = _admin().post(self.URL, _payload(sede, inicio, fin, "martes"), format="json")

        assert respuesta.status_code == 400

    def test_franjas_contiguas_si_se_permiten(self):
        sede = _sede()
        _franja(sede, "11:00", "14:00")

        respuesta = _admin().post(self.URL, _payload(sede, "14:00", "17:00"), format="json")

        assert respuesta.status_code == 201

    def test_mismo_horario_en_otro_dia_o_en_otra_sede_si_se_permite(self):
        sede, otra = _sede("Centro"), _sede("Sur")
        _franja(sede, "11:00", "14:00", "lunes")
        api = _admin()

        assert api.post(self.URL, _payload(sede, "11:00", "14:00", "martes"), format="json").status_code == 201
        assert api.post(self.URL, _payload(otra, "11:00", "14:00", "lunes"), format="json").status_code == 201

    def test_el_solape_ignora_mayusculas_y_espacios_en_los_dias(self):
        sede = _sede()
        _franja(sede, "11:00", "14:00", "lunes")

        respuesta = _admin().post(self.URL, _payload(sede, "12:00", "13:00", " Martes , LUNES "), format="json")

        assert respuesta.status_code == 400

    @pytest.mark.parametrize("inicio,fin", [("14:00", "14:00"), ("15:00", "14:00")])
    def test_la_hora_de_fin_debe_ser_posterior(self, inicio, fin):
        respuesta = _admin().post(self.URL, _payload(_sede(), inicio, fin), format="json")

        assert respuesta.status_code == 400
        assert "hora_fin" in respuesta.data

    def test_editar_una_franja_no_choca_consigo_misma(self):
        franja = _franja(_sede(), "11:00", "14:00")

        respuesta = _admin().patch(f"{self.URL}{franja.pk}/", {"max_pedidos_simultaneos": 8}, format="json")

        assert respuesta.status_code == 200


@pytest.mark.django_db
class TestDiasDeLaSemana:
    URL = "/api/capacidades/"

    def test_acepta_tildes_y_mayusculas_y_guarda_el_valor_normalizado(self):
        sede = _sede()

        respuesta = _admin().post(
            self.URL, _payload(sede, "11:00", "14:00", "Miércoles, SÁBADO"), format="json"
        )

        assert respuesta.status_code == 201
        assert CapacidadSede.objects.get().dias_semana == "miercoles,sabado"

    @pytest.mark.parametrize("dias", ["lune", "xyz", "lunes,feriado", "", " , "])
    def test_rechaza_dias_que_no_existen(self, dias):
        respuesta = _admin().post(self.URL, _payload(_sede(), "11:00", "14:00", dias), format="json")

        assert respuesta.status_code == 400
        assert "dias_semana" in respuesta.data

    def test_una_franja_creada_con_tilde_se_aplica_ese_dia(self):
        sede = _sede()
        _admin().post(self.URL, _payload(sede, "11:00", "14:00", "miércoles"), format="json")

        assert franja_actual(sede, _a_las(MIERCOLES, 12)) is not None


@pytest.mark.django_db
class TestFranjaActual:
    def test_en_el_borde_aplica_la_franja_que_empieza(self):
        sede = _sede()
        _franja(sede, "11:00", "14:00", maximo=5)
        tarde = _franja(sede, "14:00", "17:00", maximo=20)

        assert franja_actual(sede, _a_las(LUNES, 14)) == tarde

    def test_un_segundo_antes_del_borde_sigue_la_anterior(self):
        sede = _sede()
        mañana = _franja(sede, "11:00", "14:00")
        _franja(sede, "14:00", "17:00")

        assert franja_actual(sede, _a_las(LUNES, 13, 59, 59)) == mañana

    def test_la_hora_de_inicio_ya_pertenece_a_la_franja(self):
        sede = _sede()
        mañana = _franja(sede, "11:00", "14:00")

        assert franja_actual(sede, _a_las(LUNES, 11)) == mañana
        assert franja_actual(sede, _a_las(LUNES, 10, 59, 59)) is None

    def test_otro_dia_no_aplica(self):
        sede = _sede()
        _franja(sede, "11:00", "14:00", "lunes")

        assert franja_actual(sede, _a_las(MIERCOLES, 12)) is None
