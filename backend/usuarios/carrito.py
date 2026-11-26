"""
HU-21 (producto final) · Carrito guardado en el servidor.

GET /api/usuarios/carrito/   -> el carrito guardado del cliente (vacío si no tiene)
PUT /api/usuarios/carrito/   -> reemplaza el carrito guardado

En el PMV el carrito vivía solo en localStorage. Ahora el servidor guarda una copia
para que el cliente vea el mismo carrito en cualquier dispositivo. Se guarda el
mismo JSON del frontend ({sedeId, lineas, promocion}).

Aquí solo se valida la forma (y un tamaño máximo), no el menú: los precios, el
stock y la disponibilidad se vuelven a validar al crear el pedido. Solo clientes;
cada uno ve únicamente su propio carrito (se busca por request.user, no por id).
"""
import json

from django.utils.decorators import method_decorator
from django.views.decorators.cache import never_cache
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import serializers
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import CarritoGuardado
from .permissions import EsCliente

MAXIMO_LINEAS = 50
MAXIMO_BYTES = 50 * 1024  # 50 KB: un carrito normal pesa unos pocos KB


class CarritoGuardadoSerializer(serializers.Serializer):
    """Forma del carrito del frontend. Los campos de cada línea no se revisan uno a uno."""

    sedeId = serializers.IntegerField(allow_null=True, required=False, default=None)
    lineas = serializers.ListField(child=serializers.DictField(), max_length=MAXIMO_LINEAS)
    promocion = serializers.DictField(allow_null=True, required=False, default=None)
    actualizado_en = serializers.DateTimeField(read_only=True)

    def validate_lineas(self, lineas):
        for linea in lineas:
            if not linea.get("id"):
                raise serializers.ValidationError("Cada línea del carrito debe tener un id.")
        return lineas

    def validate(self, datos):
        if len(json.dumps(datos).encode("utf-8")) > MAXIMO_BYTES:
            raise serializers.ValidationError("El carrito es demasiado grande.")
        return datos


def carrito_a_datos(carrito):
    """CarritoGuardado (o None) -> diccionario para la respuesta."""
    contenido = carrito.contenido if carrito else {}
    return {
        "sedeId": contenido.get("sedeId"),
        "lineas": contenido.get("lineas", []),
        "promocion": contenido.get("promocion"),
        "actualizado_en": carrito.actualizado_en if carrito else None,
    }


@method_decorator(never_cache, name="dispatch")
class CarritoGuardadoView(APIView):
    permission_classes = [EsCliente]

    @extend_schema(
        tags=["Carrito"],
        summary="Consultar el carrito guardado (HU-21)",
        responses={200: CarritoGuardadoSerializer, 403: OpenApiResponse(description="No es cliente.")},
    )
    def get(self, request):
        carrito = CarritoGuardado.objects.filter(cliente=request.user.cliente).first()
        return Response(CarritoGuardadoSerializer(carrito_a_datos(carrito)).data)

    @extend_schema(
        tags=["Carrito"],
        summary="Guardar el carrito (HU-21)",
        description=f"Reemplaza el carrito guardado. Máximo {MAXIMO_LINEAS} líneas y 50 KB.",
        request=CarritoGuardadoSerializer,
        responses={
            200: CarritoGuardadoSerializer,
            400: OpenApiResponse(description="Forma inválida, demasiadas líneas o demasiado grande."),
            403: OpenApiResponse(description="No es cliente."),
        },
    )
    def put(self, request):
        serializer = CarritoGuardadoSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        datos = serializer.validated_data
        carrito, _ = CarritoGuardado.objects.update_or_create(
            cliente=request.user.cliente,
            defaults={"contenido": {
                "sedeId": datos.get("sedeId"),
                "lineas": datos["lineas"],
                "promocion": datos.get("promocion"),
            }},
        )
        return Response(CarritoGuardadoSerializer(carrito_a_datos(carrito)).data)
