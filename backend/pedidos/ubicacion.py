"""
HU-38 · Mapa de pedidos en camino (operador).

El celular del repartidor envía su ubicación cada 30 segundos, SOLO mientras lleva un
pedido (recogido o en camino): fuera de una entrega no se rastrea a nadie.

    POST /api/pedidos/mis-entregas/ubicacion/     {"latitud": 3.45, "longitud": -76.53}
        repartidor; 204. Sin entrega en curso → 409.

El operador ve en un mapa los pedidos "En camino" de su sede con la última ubicación de
cada repartidor; la pantalla se actualiza sola cada 30 segundos.

    GET /api/pedidos/en-camino/mapa/              operador (su sede) o administrador (?sede=)

HU-49 · El cliente ve en un mapa dónde va el repartidor de SU pedido, solo mientras está
"En camino" (antes o después no se expone la ubicación de nadie).

    GET /api/pedidos/mios/<id>/ubicacion/         cliente dueño del pedido

Una ubicación de hace más de UMBRAL_SIN_SENAL se marca como "sin señal" (el celular
perdió el GPS, la conexión o cerró la app): el punto se sigue mostrando, pero atenuado.
"""
from datetime import timedelta

from django.shortcuts import get_object_or_404
from django.utils import timezone
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework import serializers, status
from rest_framework.response import Response
from rest_framework.views import APIView

from sedes.models import Sede
from usuarios.models import Repartidor
from usuarios.permissions import EsCliente, EsRepartidor, rol_requerido
from usuarios.roles import ADMINISTRADOR, OPERADOR, REPARTIDOR, obtener_rol, obtener_sede

from .estados import CLIENTE
from .models import EstadoPedido
from .views import pedidos_visibles

INTERVALO_SEGUNDOS = 30
UMBRAL_SIN_SENAL = timedelta(minutes=2)
ESTADOS_RASTREO = (EstadoPedido.RECOGIDO, EstadoPedido.EN_CAMINO)


# --- El repartidor envía su ubicación ---------------------------------------------------


class UbicacionSerializer(serializers.Serializer):
    latitud = serializers.FloatField(min_value=-90, max_value=90)
    longitud = serializers.FloatField(min_value=-180, max_value=180)


class UbicacionRepartidorView(APIView):
    permission_classes = [EsRepartidor]

    @extend_schema(
        tags=["Entregas"],
        summary="Enviar la ubicación del repartidor (HU-38)",
        description=(
            f"El celular la envía cada {INTERVALO_SEGUNDOS} s mientras el repartidor lleva un pedido "
            "(recogido o en camino). Fuera de una entrega responde 409 y no se guarda."
        ),
        request=UbicacionSerializer,
        responses={204: None, 400: OpenApiResponse(description="Coordenadas inválidas."),
                   409: OpenApiResponse(description="No lleva ningún pedido.")},
    )
    def post(self, request):
        datos = UbicacionSerializer(data=request.data)
        datos.is_valid(raise_exception=True)
        lleva_pedido = pedidos_visibles(request.user, REPARTIDOR).filter(estado__in=ESTADOS_RASTREO).exists()
        if not lleva_pedido:
            return Response(
                {"detail": "La ubicación solo se comparte mientras llevas un pedido."},
                status=status.HTTP_409_CONFLICT,
            )
        Repartidor.objects.filter(empleado__usuario=request.user).update(
            latitud=datos.validated_data["latitud"],
            longitud=datos.validated_data["longitud"],
            ubicacion_actualizada_en=timezone.now(),
        )
        return Response(status=status.HTTP_204_NO_CONTENT)


# --- El operador ve el mapa ------------------------------------------------------------


def _punto(latitud, longitud):
    if latitud is None or longitud is None:
        return None
    return {"latitud": latitud, "longitud": longitud}


def entregas_en_camino(pedidos, ahora):
    filas = []
    for pedido in pedidos:
        repartidor = pedido.repartidor
        actualizada = repartidor.ubicacion_actualizada_en if repartidor else None
        filas.append({
            "pedido_id": pedido.pk,
            "numero_pedido": pedido.numero_pedido,
            "repartidor": (
                f"{repartidor.empleado.nombres} {repartidor.empleado.apellidos}".strip() if repartidor else None
            ),
            "ubicacion": _punto(repartidor.latitud, repartidor.longitud) if actualizada else None,
            "ubicacion_actualizada_en": actualizada,
            "sin_senal": actualizada is None or ahora - actualizada > UMBRAL_SIN_SENAL,
            "destino": _punto(pedido.entrega_latitud, pedido.entrega_longitud),
            "destino_direccion": pedido.entrega_direccion,
            "destino_barrio": pedido.entrega_barrio,
        })
    return filas


class PuntoSerializer(serializers.Serializer):
    latitud = serializers.FloatField()
    longitud = serializers.FloatField()


class SedeMapaSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    nombre = serializers.CharField()
    ubicacion = PuntoSerializer(allow_null=True)


class EntregaEnCaminoSerializer(serializers.Serializer):
    pedido_id = serializers.IntegerField()
    numero_pedido = serializers.CharField()
    repartidor = serializers.CharField(allow_null=True)
    ubicacion = PuntoSerializer(allow_null=True, help_text="Última posición del repartidor.")
    ubicacion_actualizada_en = serializers.DateTimeField(allow_null=True)
    sin_senal = serializers.BooleanField(help_text="Sin ubicación o con más de 2 minutos.")
    destino = PuntoSerializer(allow_null=True)
    destino_direccion = serializers.CharField()
    destino_barrio = serializers.CharField()


class MapaEnCaminoSerializer(serializers.Serializer):
    sede = SedeMapaSerializer(allow_null=True)
    intervalo_segundos = serializers.IntegerField()
    entregas = EntregaEnCaminoSerializer(many=True)


class MapaEnCaminoView(APIView):
    permission_classes = [rol_requerido(OPERADOR, ADMINISTRADOR)]

    @extend_schema(
        tags=["Entregas"],
        summary="Mapa de pedidos en camino (HU-38)",
        description=(
            "Pedidos \"En camino\" de la sede con la última ubicación de su repartidor. "
            "El operador ve su sede; el administrador elige con `?sede=` (sin ella, todas)."
        ),
        parameters=[OpenApiParameter("sede", int, description="Solo administrador.")],
        responses={200: MapaEnCaminoSerializer, 404: OpenApiResponse(description="La sede no existe.")},
    )
    def get(self, request):
        rol = obtener_rol(request.user)
        pedidos = pedidos_visibles(request.user, rol).filter(estado=EstadoPedido.EN_CAMINO)
        sede = obtener_sede(request.user)
        if rol == ADMINISTRADOR:
            texto_sede = request.query_params.get("sede")
            sede = get_object_or_404(Sede, pk=texto_sede) if texto_sede and texto_sede.isdigit() else None
            if sede:
                pedidos = pedidos.filter(sede=sede)

        pedidos = pedidos.select_related("repartidor__empleado").order_by("id")
        return Response(MapaEnCaminoSerializer({
            "sede": sede and {
                "id": sede.pk, "nombre": sede.nombre, "ubicacion": _punto(sede.latitud, sede.longitud),
            },
            "intervalo_segundos": INTERVALO_SEGUNDOS,
            "entregas": entregas_en_camino(pedidos, timezone.now()),
        }).data)


# --- HU-49 · El cliente ve al repartidor de su pedido ----------------------------------


class UbicacionPedidoClienteSerializer(serializers.Serializer):
    estado = serializers.CharField()
    rastreando = serializers.BooleanField(help_text="True solo con el pedido en camino.")
    intervalo_segundos = serializers.IntegerField()
    repartidor = serializers.CharField(allow_null=True, help_text="Solo el primer nombre.")
    ubicacion = PuntoSerializer(allow_null=True)
    ubicacion_actualizada_en = serializers.DateTimeField(allow_null=True)
    sin_senal = serializers.BooleanField()
    destino = PuntoSerializer(allow_null=True)


def ubicacion_para_cliente(pedido, ahora):
    rastreando = pedido.estado == EstadoPedido.EN_CAMINO
    repartidor = pedido.repartidor if rastreando else None
    actualizada = repartidor.ubicacion_actualizada_en if repartidor else None
    return {
        "estado": pedido.estado,
        "rastreando": rastreando,
        "intervalo_segundos": INTERVALO_SEGUNDOS,
        "repartidor": repartidor.empleado.nombres.split()[0] if repartidor and repartidor.empleado.nombres else None,
        "ubicacion": _punto(repartidor.latitud, repartidor.longitud) if actualizada else None,
        "ubicacion_actualizada_en": actualizada,
        "sin_senal": rastreando and (actualizada is None or ahora - actualizada > UMBRAL_SIN_SENAL),
        "destino": _punto(pedido.entrega_latitud, pedido.entrega_longitud) if rastreando else None,
    }


class UbicacionPedidoClienteView(APIView):
    permission_classes = [EsCliente]

    @extend_schema(
        tags=["Pedidos"],
        summary="Ubicación del repartidor de mi pedido (HU-49)",
        description=(
            "Mientras el pedido está \"En camino\" devuelve la última ubicación del repartidor y el "
            "destino. En cualquier otro estado `rastreando` es false y no se envía ninguna ubicación."
        ),
        responses={200: UbicacionPedidoClienteSerializer, 404: OpenApiResponse(description="No es tu pedido.")},
    )
    def get(self, request, pk):
        pedido = get_object_or_404(
            pedidos_visibles(request.user, CLIENTE).select_related("repartidor__empleado"), pk=pk
        )
        return Response(UbicacionPedidoClienteSerializer(ubicacion_para_cliente(pedido, timezone.now())).data)
