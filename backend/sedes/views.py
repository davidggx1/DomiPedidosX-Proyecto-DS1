import math
from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from .models import Ciudad, Sede, HorarioSede, Feriado, ZonaCobertura, CapacidadSede
from .serializers import (
    SedeSerializer, CiudadSerializer, HorarioSedeSerializer, FeriadoSerializer, CapacidadSedeSerializer, ZonaCoberturaSerializer
)
from django.db.models import ProtectedError
from drf_spectacular.utils import extend_schema
from rest_framework.exceptions import APIException

from usuarios.roles import ADMINISTRADOR, obtener_rol

# Permiso personalizado
class EsAdministradorPermission(permissions.BasePermission):
    """Permite mutaciones (POST, PUT, DELETE) solo a usuarios autenticados como Administrador."""
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        return request.user.is_staff or obtener_rol(request.user) == ADMINISTRADOR


# ---------------------------------------------------------------------------
# Algoritmo Geográfico de Cobertura (Haversine + Point-in-Polygon Ray-Casting)
# ---------------------------------------------------------------------------
def calcular_distancia_haversine(lat1, lon1, lat2, lon2):
    """Calcula la distancia en kilómetros entre dos coordenadas usando Haversine."""
    R = 6371.0  # Radio de la Tierra en km
    rad_lat1, rad_lon1 = math.radians(lat1), math.radians(lon1)
    rad_lat2, rad_lon2 = math.radians(lat2), math.radians(lon2)

    dlat = rad_lat2 - rad_lat1
    dlon = rad_lon2 - rad_lon1

    a = math.sin(dlat / 2) ** 2 + math.cos(rad_lat1) * math.cos(rad_lat2) * math.sin(dlon / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


def punto_en_poligono(lat, lon, vertices):
    """
    Algoritmo Ray-Casting (Punto en Polígono).
    vertices = [{'latitud': y, 'longitud': x}, ...] o [[lat, lon], ...]
    """
    dentro = False
    n = len(vertices)
    if n < 3:
        return False

    j = n - 1
    for i in range(n):
        v_i = vertices[i]
        v_j = vertices[j]

        lat_i = v_i['latitud'] if isinstance(v_i, dict) else v_i[0]
        lon_i = v_i['longitud'] if isinstance(v_i, dict) else v_i[1]
        lat_j = v_j['latitud'] if isinstance(v_j, dict) else v_j[0]
        lon_j = v_j['longitud'] if isinstance(v_j, dict) else v_j[1]

        if ((lon_i > lon) != (lon_j > lon)) and \
                (lat < (lat_j - lat_i) * (lon - lon_i) / (lon_j - lon_i + 1e-12) + lat_i):
            dentro = not dentro
        j = i

    return dentro


def evaluar_cobertura_sede(lat, lon, sede):
    """
    Evalúa si un punto (lat, lon) cae dentro de la cobertura de una sede.
    Soporta polígonos explícitos o zonas circulares (ZonaCobertura / Radio Sede).
    Retorna (esta_cubierto, distancia_km, zona_cobertura_obj)
    """
    zonas = sede.zonas_cobertura.filter(activo=True)

    # 1. Si la sede posee zonas de cobertura configuradas
    if zonas.exists():
        mejores_coincidencias = []
        for zona in zonas:
            # Si la zona define polígono explícito
            vertices = getattr(zona, 'poligono_vertices', None)
            if vertices and len(vertices) >= 3:
                if punto_en_poligono(lat, lon, vertices):
                    dist = calcular_distancia_haversine(lat, lon, zona.centro_latitud, zona.centro_longitud)
                    mejores_coincidencias.append((True, dist, zona))
            else:
                # Cobertura por Radio Circular
                dist = calcular_distancia_haversine(lat, lon, zona.centro_latitud, zona.centro_longitud)
                if dist <= zona.radio:
                    mejores_coincidencias.append((True, dist, zona))

        if mejores_coincidencias:
            # Retorna la zona con menor distancia al centro
            mejores_coincidencias.sort(key=lambda x: x[1])
            return mejores_coincidencias[0]

    # 2. Fallback: Proximidad directa al punto central de la Sede (Radio por defecto 5.0 km)
    dist_sede = calcular_distancia_haversine(lat, lon, sede.latitud, sede.longitud)
    radio_default = getattr(sede, 'radio_cobertura', 5.0)
    if dist_sede <= radio_default:
        return True, dist_sede, None

    return False, dist_sede, None


# ViewSet de Sedes
class SedeViewSet(viewsets.ModelViewSet):
    queryset = Sede.objects.select_related('ciudad').all()
    serializer_class = SedeSerializer

    def get_permissions(self):
        if self.action in ['list', 'retrieve', 'validar_cobertura']:
            return [permissions.AllowAny()]
        return [EsAdministradorPermission()]

    def get_queryset(self):
        queryset = super().get_queryset()
        activa_param = self.request.query_params.get('activa', None)

        if activa_param is not None:
            # Convierte adecuadamente booleanos y strings ('true', 'True', '1')
            es_activa = str(activa_param).lower() in ['true', '1']
            queryset = queryset.filter(activa=es_activa)

        return queryset

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        nuevo_estado_activo = request.data.get('activa', instance.activa)
        confirmar_desactivacion = request.data.get('confirmar_desactivacion', False)

        if instance.activa and not nuevo_estado_activo:
            serializer = self.get_serializer(instance)
            if serializer.data['tiene_pedidos_pendientes'] and not confirmar_desactivacion:
                return Response(
                    {
                        "warning": True,
                        "message": (
                            f"La sede '{instance.nombre}' tiene pedidos pendientes por entregar. "
                            "¿Desea confirmar la desactivación?"
                        )
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )

        return super().update(request, *args, **kwargs)

    @action(detail=False, methods=['post'], url_path='validar-cobertura')
    def validar_cobertura(self, request):
        """
        HU-58: Valida la latitud y longitud enviada por el cliente.
        Body: { "latitud": 3.45, "longitud": -76.53 }
        """
        try:
            lat = float(request.data.get('latitud'))
            lon = float(request.data.get('longitud'))
        except (TypeError, ValueError):
            return Response(
                {"detail": "Se requieren las coordenadas 'latitud' y 'longitud' válidas."},
                status=status.HTTP_400_BAD_REQUEST
            )

        sedes_activas = Sede.objects.filter(activa=True).prefetch_related('zonas_cobertura')
        if not sedes_activas.exists():
            return Response({
                "cubierto": False,
                "mensaje": "No hay sedes activas en el sistema."
            }, status=status.HTTP_200_OK)

        sedes_con_cobertura = []

        for sede in sedes_activas:
            cubierto, dist_km, zona = evaluar_cobertura_sede(lat, lon, sede)
            if cubierto:
                sedes_con_cobertura.append({
                    'sede': sede,
                    'distancia_km': dist_km,
                    'zona': zona
                })

        # Criterio 2: Fuera de todas las áreas
        if not sedes_con_cobertura:
            sede_mas_cercana = min(
                sedes_activas,
                key=lambda s: calcular_distancia_haversine(lat, lon, s.latitud, s.longitud)
            )
            dist_min = calcular_distancia_haversine(lat, lon, sede_mas_cercana.latitud, sede_mas_cercana.longitud)

            return Response({
                "cubierto": False,
                "mensaje": f"Tu ubicación está fuera de nuestra zona de cobertura. La sede activa más cercana es {sede_mas_cercana.nombre} a {dist_min:.2f} km.",
                "sede_mas_cercana": {
                    "id": sede_mas_cercana.id,
                    "nombre": sede_mas_cercana.nombre,
                    "distancia_km": round(dist_min, 2)
                }
            }, status=status.HTTP_200_OK)

        # Criterio 3: Asignar a la sede activa geográficamente más cercana entre las que cubren la zona
        sedes_con_cobertura.sort(key=lambda item: item['distancia_km'])
        ganadora = sedes_con_cobertura[0]
        sede_asignada = ganadora['sede']
        zona_asignada = ganadora['zona']

        return Response({
            "cubierto": True,
            "mensaje": f"Dirección con cobertura confirmada para {sede_asignada.nombre}.",
            "sede": {
                "id": sede_asignada.id,
                "nombre": sede_asignada.nombre,
                "direccion": sede_asignada.direccion,
                "distancia_km": round(ganadora['distancia_km'], 2),
                "tarifa_domicilio": float(zona_asignada.tarifa_domicilio) if zona_asignada else 0.0,
                "pedido_minimo": float(zona_asignada.pedido_minimo) if zona_asignada else 0.0,
                "tiempo_estimado": zona_asignada.tiempo_estimado if zona_asignada else 30,
            }
        }, status=status.HTTP_200_OK)


# ViewSet de Horarios (HU-82)
class HorarioSedeViewSet(viewsets.ModelViewSet):
    queryset = HorarioSede.objects.all()
    serializer_class = HorarioSedeSerializer
    permission_classes = [EsAdministradorPermission]

    def get_queryset(self):
        queryset = super().get_queryset()
        sede_id = self.request.query_params.get('sede', None)
        if sede_id:
            queryset = queryset.filter(sede_id=sede_id)
        return queryset


# ViewSet de Feriados (HU-82)
class FeriadoViewSet(viewsets.ModelViewSet):
    queryset = Feriado.objects.all()
    serializer_class = FeriadoSerializer
    permission_classes = [EsAdministradorPermission]

    def get_queryset(self):
        queryset = super().get_queryset()
        sede_id = self.request.query_params.get('sede', None)
        if sede_id:
            queryset = queryset.filter(sede_id=sede_id)
        return queryset

class CiudadViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Ciudad.objects.all()
    serializer_class = CiudadSerializer
    permission_classes = [permissions.AllowAny]

class CapacidadSedeViewSet(viewsets.ModelViewSet):
    queryset = CapacidadSede.objects.all()
    serializer_class = CapacidadSedeSerializer
    permission_classes = [EsAdministradorPermission]

    def get_queryset(self):
        queryset = super().get_queryset()
        sede_id = self.request.query_params.get('sede', None)
        if sede_id:
            queryset = queryset.filter(sede_id=sede_id)
        return queryset




class ZonaEnUso(APIException):
    status_code = 409
    default_code = "zona_en_uso"
    default_detail = (
        "Esta zona tiene pedidos asociados y no se puede eliminar. Desactívala en su lugar."
    )


@extend_schema(tags=["Zonas de cobertura"])
class ZonaCoberturaViewSet(viewsets.ModelViewSet):
    """HU-55: zonas de cobertura por radio o polígono (solo administrador).

    Los cambios aplican a pedidos futuros: cada pedido conserva su tiempo estimado y la
    factura su costo de domicilio. Una zona con pedidos no se elimina, se desactiva.
    Filtros: `?sede=<id>` y `?activo=true|false`.
    """

    queryset = ZonaCobertura.objects.select_related("sede").order_by("sede_id", "id")
    serializer_class = ZonaCoberturaSerializer
    permission_classes = [EsAdministradorPermission]

    def get_queryset(self):
        queryset = super().get_queryset()
        sede_id = self.request.query_params.get("sede")
        if sede_id:
            queryset = queryset.filter(sede_id=sede_id)
        activo = self.request.query_params.get("activo")
        if activo is not None:
            queryset = queryset.filter(activo=str(activo).lower() in ["true", "1"])
        return queryset

    def perform_destroy(self, instance):
        try:
            instance.delete()
        except ProtectedError:
            raise ZonaEnUso()