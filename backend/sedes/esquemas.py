"""
SCRUM-120 · Formas de petición y respuesta para la documentación de la API.

Estos serializers no validan ni guardan nada: solo le dicen a drf-spectacular
(Swagger en /api/docs/) qué recibe y qué devuelve cada endpoint cuando la vista
arma la respuesta a mano con un diccionario.
"""
from rest_framework import serializers


class ErrorDetalleSerializer(serializers.Serializer):
    """Error estándar de la API: un mensaje listo para mostrar al usuario."""

    detail = serializers.CharField()


class ValidarCoberturaSolicitudSerializer(serializers.Serializer):
    latitud = serializers.FloatField(min_value=-90, max_value=90, help_text="Latitud de la dirección del cliente.")
    longitud = serializers.FloatField(min_value=-180, max_value=180, help_text="Longitud de la dirección del cliente.")


class SedeCubiertaSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    nombre = serializers.CharField()
    direccion = serializers.CharField()
    distancia_km = serializers.FloatField(help_text="Distancia al centro de la zona que cubre la dirección.")
    tarifa_domicilio = serializers.FloatField(help_text="Costo de domicilio de la zona (HU-56).")
    pedido_minimo = serializers.FloatField(
        help_text="Subtotal mínimo de productos para pedir en la zona, sin el domicilio (HU-57). 0 = sin mínimo."
    )
    tiempo_estimado = serializers.IntegerField(help_text="Tiempo base de entrega de la zona, en minutos.")


class SedeMasCercanaSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    nombre = serializers.CharField()
    distancia_km = serializers.FloatField()


class ValidarCoberturaRespuestaSerializer(serializers.Serializer):
    cubierto = serializers.BooleanField()
    mensaje = serializers.CharField()
    sede = SedeCubiertaSerializer(
        required=False, help_text="Solo si `cubierto` es true: la sede asignada (la más cercana que cubre la dirección)."
    )
    sede_mas_cercana = SedeMasCercanaSerializer(
        required=False, help_text="Solo si `cubierto` es false: la sede activa más cercana, como referencia."
    )
