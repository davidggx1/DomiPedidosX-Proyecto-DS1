import math
from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from .models import Ciudad, Sede, HorarioSede, Feriado, ZonaCobertura, CapacidadSede
from .serializers import (
    SedeSerializer, CiudadSerializer, HorarioSedeSerializer, FeriadoSerializer, CapacidadSedeSerializer, ZonaCoberturaSerializer
)
from django.db.models import ProtectedError
from drf_spectacular.utils import (
    OpenApiExample,
    OpenApiParameter,
    OpenApiResponse,
    extend_schema,
    extend_schema_view,
)
from rest_framework.exceptions import APIException

from usuarios.roles import ADMINISTRADOR, obtener_rol

from .esquemas import (
    ErrorDetalleSerializer,
    ValidarCoberturaRespuestaSerializer,
    ValidarCoberturaSolicitudSerializer,
)
from .geometria import contiene_punto

# Permiso personalizado
class EsAdministradorPermission(permissions.BasePermission):
    """Permite mutaciones (POST, PUT, DELETE) solo a usuarios autenticados como Administrador."""
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        return request.user.is_staff or obtener_rol(request.user) == ADMINISTRADOR


# ---------------------------------------------------------------------------
# Cobertura geográfica (HU-58): distancia Haversine + zonas de sedes/geometria.py
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


def evaluar_cobertura_sede(lat, lon, sede):
    """
    Evalúa si un punto (lat, lon) cae dentro de alguna zona activa de la sede.
    Retorna (esta_cubierto, distancia_km, zona_cobertura_obj).

    Usa la misma regla que la confirmación del pedido (sedes/geometria.py, que
    también usa pedidos/servicios.py), para que el cliente no reciba "con cobertura"
    aquí y luego un rechazo al pagar (SCRUM-121). Sin zonas activas no hay cobertura.
    """
    coincidencias = [
        (calcular_distancia_haversine(lat, lon, zona.centro_latitud, zona.centro_longitud), zona)
        for zona in sede.zonas_cobertura.filter(activo=True)
        if contiene_punto(
            lat, lon, zona.centro_latitud, zona.centro_longitud, zona.radio, zona.poligono_vertices
        )
    ]
    if not coincidencias:
        return False, calcular_distancia_haversine(lat, lon, sede.latitud, sede.longitud), None

    # La zona con el centro más cercano al cliente
    distancia, zona = min(coincidencias, key=lambda item: item[0])
    return True, distancia, zona


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

    @extend_schema(
        tags=["Cobertura"],
        summary="Validar si una dirección tiene cobertura (HU-58)",
        description=(
            "El cliente la consulta **antes de pagar**. Revisa las zonas de cobertura activas "
            "de todas las sedes activas y responde con la sede asignada (la más cercana que "
            "cubre la dirección), su tarifa de domicilio y su tiempo base.\n\n"
            "Usa la misma regla que la confirmación del pedido: si aquí responde "
            "`cubierto: true`, la confirmación no rechazará la dirección por cobertura. "
            "No requiere iniciar sesión."
        ),
        request=ValidarCoberturaSolicitudSerializer,
        responses={
            200: ValidarCoberturaRespuestaSerializer,
            400: OpenApiResponse(ErrorDetalleSerializer, description="Faltan las coordenadas o no son números."),
        },
        examples=[
            OpenApiExample(
                "Dirección con cobertura",
                response_only=True,
                value={
                    "cubierto": True,
                    "mensaje": "Dirección con cobertura confirmada para Sede Centro.",
                    "sede": {
                        "id": 1, "nombre": "Sede Centro", "direccion": "Calle 5 # 38-14",
                        "distancia_km": 0.84, "tarifa_domicilio": 5000.0, "pedido_minimo": 15000.0,
                        "tiempo_estimado": 30,
                    },
                },
            ),
            OpenApiExample(
                "Dirección fuera de cobertura",
                response_only=True,
                value={
                    "cubierto": False,
                    "mensaje": "Tu ubicación está fuera de nuestra zona de cobertura. "
                               "La sede activa más cercana es Sede Centro a 7.12 km.",
                    "sede_mas_cercana": {"id": 1, "nombre": "Sede Centro", "distancia_km": 7.12},
                },
            ),
            OpenApiExample("Coordenadas", request_only=True, value={"latitud": 3.4516, "longitud": -76.532}),
        ],
    )
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

_FILTRO_SEDE = OpenApiParameter("sede", int, description="Solo las de esta sede.")
_NO_ES_ADMIN = OpenApiResponse(description="No inició sesión o no es administrador.")
_REGLAS_FRANJA = (
    "Reglas (HU-59):\n"
    "- `hora_inicio` debe ser anterior a `hora_fin`. Una franja cubre [inicio, fin): con 11:00-14:00 "
    "y 14:00-17:00, las 14:00 pertenecen a la segunda.\n"
    "- `dias_semana` es una lista separada por comas (`lunes,martes`). Acepta tildes y mayúsculas "
    "y se guarda normalizada; rechaza días que no existen.\n"
    "- Dos franjas de la misma sede no pueden cruzarse en hora si comparten algún día. "
    "Las contiguas sí se permiten.\n"
    "- `max_pedidos_simultaneos` ≥ 1. Cuentan los pedidos pendientes de aprobación, recibidos "
    "y en preparación (HU-61). Desde `umbral_alerta` pedidos se alerta al operador (HU-60)."
)


@extend_schema_view(
    list=extend_schema(summary="Listar franjas de capacidad", parameters=[_FILTRO_SEDE],
                       responses={200: CapacidadSedeSerializer(many=True), 403: _NO_ES_ADMIN}),
    retrieve=extend_schema(summary="Ver una franja de capacidad", responses={200: CapacidadSedeSerializer, 403: _NO_ES_ADMIN}),
    create=extend_schema(summary="Crear una franja de capacidad", description=_REGLAS_FRANJA,
                         responses={201: CapacidadSedeSerializer, 400: OpenApiResponse(description="Datos inválidos o la franja se cruza con otra."), 403: _NO_ES_ADMIN}),
    update=extend_schema(summary="Reemplazar una franja de capacidad", description=_REGLAS_FRANJA,
                         responses={200: CapacidadSedeSerializer, 400: OpenApiResponse(description="Datos inválidos o la franja se cruza con otra."), 403: _NO_ES_ADMIN}),
    partial_update=extend_schema(summary="Editar campos de una franja de capacidad", description=_REGLAS_FRANJA,
                                 responses={200: CapacidadSedeSerializer, 400: OpenApiResponse(description="Datos inválidos o la franja se cruza con otra."), 403: _NO_ES_ADMIN}),
    destroy=extend_schema(summary="Eliminar una franja de capacidad", responses={204: None, 403: _NO_ES_ADMIN}),
)
@extend_schema(tags=["Capacidad"])
class CapacidadSedeViewSet(viewsets.ModelViewSet):
    """HU-59: franjas de capacidad por sede, día y hora (solo administrador)."""

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


_FILTROS_ZONA = [
    OpenApiParameter("sede", int, description="Solo las zonas de esta sede."),
    OpenApiParameter("activo", bool, description="`true` solo activas, `false` solo inactivas."),
]
_REGLAS_ZONA = (
    "Dos formas de definir la zona (HU-55):\n"
    "- **Por radio:** `radio` (km, > 0), `centro_latitud` y `centro_longitud`.\n"
    "- **Por polígono:** `poligono_vertices` como `[[lat, lon], ...]`, mínimo 3 puntos distintos, "
    "sin cruzarse consigo mismo y con área. El centro y el radio se calculan solos.\n\n"
    "Dos zonas activas de la misma sede no pueden traslaparse (tocarse en el borde sí se permite). "
    "Sin `tarifa_domicilio` y `tiempo_estimado` la zona no puede quedar activa (HU-56). "
    "`pedido_minimo` es el subtotal mínimo para pedir en la zona (HU-57)."
)
_ZONA_INVALIDA = OpenApiResponse(description="Datos inválidos, polígono inválido o la zona se traslapa con otra.")


@extend_schema_view(
    list=extend_schema(summary="Listar zonas de cobertura", parameters=_FILTROS_ZONA,
                       responses={200: ZonaCoberturaSerializer(many=True), 403: _NO_ES_ADMIN}),
    retrieve=extend_schema(summary="Ver una zona de cobertura", responses={200: ZonaCoberturaSerializer, 403: _NO_ES_ADMIN}),
    create=extend_schema(
        summary="Crear una zona de cobertura", description=_REGLAS_ZONA,
        responses={201: ZonaCoberturaSerializer, 400: _ZONA_INVALIDA, 403: _NO_ES_ADMIN},
        examples=[
            OpenApiExample("Zona por radio", request_only=True, value={
                "sede": 1, "nombre": "Centro 5 km", "radio": 5, "centro_latitud": 3.4516,
                "centro_longitud": -76.532, "tarifa_domicilio": "5000", "tiempo_estimado": 30,
                "pedido_minimo": "0", "activo": True,
            }),
            OpenApiExample("Zona por polígono", request_only=True, value={
                "sede": 1, "nombre": "San Antonio",
                "poligono_vertices": [[3.444, -76.540], [3.444, -76.528], [3.452, -76.528], [3.452, -76.540]],
                "tarifa_domicilio": "4000", "tiempo_estimado": 25, "pedido_minimo": "15000", "activo": True,
            }),
        ],
    ),
    update=extend_schema(summary="Reemplazar una zona de cobertura", description=_REGLAS_ZONA,
                         responses={200: ZonaCoberturaSerializer, 400: _ZONA_INVALIDA, 403: _NO_ES_ADMIN}),
    partial_update=extend_schema(summary="Editar campos de una zona de cobertura", description=_REGLAS_ZONA,
                                 responses={200: ZonaCoberturaSerializer, 400: _ZONA_INVALIDA, 403: _NO_ES_ADMIN}),
    destroy=extend_schema(
        summary="Eliminar una zona de cobertura",
        responses={
            204: None,
            403: _NO_ES_ADMIN,
            409: OpenApiResponse(ErrorDetalleSerializer, description="La zona tiene pedidos: desactívala en su lugar."),
        },
    ),
)
@extend_schema(tags=["Cobertura"])
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