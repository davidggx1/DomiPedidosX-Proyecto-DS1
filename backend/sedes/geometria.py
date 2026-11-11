"""Geometría de zonas de cobertura (radio o polígono). Coordenadas en grados; áreas en km²."""
import math

from shapely.geometry import Point, Polygon

RADIO_TIERRA_KM = 6371.0088
# Traslape mínimo para considerar que dos zonas se cruzan (1 m²): tocarse en un borde no cuenta.
AREA_MINIMA_TRASLAPE_KM2 = 1e-6
MAX_VERTICES = 200


def distancia_km(lat1, lon1, lat2, lon2):
    """Distancia Haversine en km."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    a = (
        math.sin((p2 - p1) / 2) ** 2
        + math.cos(p1) * math.cos(p2) * math.sin(math.radians(lon2 - lon1) / 2) ** 2
    )
    return 2 * RADIO_TIERRA_KM * math.asin(math.sqrt(min(1.0, a)))


def _plano(lat, lon, lat0, lon0):
    """Proyección plana (km) alrededor de (lat0, lon0); precisa para escala de ciudad."""
    x = math.radians(lon - lon0) * RADIO_TIERRA_KM * math.cos(math.radians(lat0))
    y = math.radians(lat - lat0) * RADIO_TIERRA_KM
    return x, y


def _forma(zona, lat0, lon0):
    """zona = (centro_latitud, centro_longitud, radio_km, vertices | None)."""
    centro_lat, centro_lon, radio, vertices = zona
    if vertices:
        return Polygon([_plano(la, lo, lat0, lon0) for la, lo in vertices])
    x, y = _plano(centro_lat, centro_lon, lat0, lon0)
    return Point(x, y).buffer(radio, 32)


def normalizar_poligono(vertices):
    """Valida el polígono y lo devuelve como lista de [lat, lon] sin repetir el cierre.

    Acepta el anillo abierto o cerrado (primer punto repetido al final).
    Lanza ValueError con un mensaje para el usuario si no es válido.
    """
    if not isinstance(vertices, (list, tuple)):
        raise ValueError("El polígono debe ser una lista de puntos [latitud, longitud].")
    if len(vertices) > MAX_VERTICES:
        raise ValueError(f"El polígono admite como máximo {MAX_VERTICES} puntos.")

    puntos = []
    for punto in vertices:
        if (
            not isinstance(punto, (list, tuple))
            or len(punto) != 2
            or not all(isinstance(c, (int, float)) and not isinstance(c, bool) for c in punto)
        ):
            raise ValueError("Cada punto del polígono debe ser [latitud, longitud].")
        lat, lon = float(punto[0]), float(punto[1])
        if not (-90 <= lat <= 90 and -180 <= lon <= 180):
            raise ValueError("Hay coordenadas fuera de rango en el polígono.")
        if puntos and puntos[-1] == [lat, lon]:
            continue
        puntos.append([lat, lon])

    if len(puntos) > 1 and puntos[0] == puntos[-1]:
        puntos.pop()
    if len(puntos) < 3:
        raise ValueError(
            "El polígono está abierto o incompleto: necesita al menos 3 puntos distintos."
        )

    plano = Polygon([_plano(la, lo, puntos[0][0], puntos[0][1]) for la, lo in puntos])
    if not plano.is_valid:
        raise ValueError("El polígono se cruza consigo mismo.")
    if plano.area < AREA_MINIMA_TRASLAPE_KM2:
        raise ValueError("El polígono no encierra un área.")
    return puntos


def envolvente(vertices):
    """(centro_lat, centro_lon, radio_km) de un círculo que contiene todo el polígono."""
    lat = sum(v[0] for v in vertices) / len(vertices)
    lon = sum(v[1] for v in vertices) / len(vertices)
    radio = max(distancia_km(lat, lon, v[0], v[1]) for v in vertices)
    return lat, lon, radio


def traslapan(zona_a, zona_b):
    """True si las dos zonas comparten área (tocarse en el borde no cuenta)."""
    lat0, lon0 = zona_a[0], zona_a[1]
    interseccion = _forma(zona_a, lat0, lon0).intersection(_forma(zona_b, lat0, lon0))
    return interseccion.area > AREA_MINIMA_TRASLAPE_KM2


def contiene_punto(lat, lon, centro_latitud, centro_longitud, radio, vertices=None):
    """True si el punto está dentro de la zona (borde incluido)."""
    if vertices:
        zona = (centro_latitud, centro_longitud, radio, vertices)
        return _forma(zona, lat, lon).covers(Point(0, 0))
    return distancia_km(lat, lon, centro_latitud, centro_longitud) <= radio