from rest_framework import serializers
from .models import MetodoPago, OrigenPedido
from .serializers_confirmar import ItemCarritoSerializer


class CrearPedidoOperadorSerializer(serializers.Serializer):
    origen = serializers.ChoiceField(
        choices=[OrigenPedido.TELEFONICO, OrigenPedido.MOSTRADOR],
        error_messages={"invalid_choice": "El origen debe ser 'telefonico' o 'mostrador'."},
    )
    cliente_id = serializers.IntegerField(min_value=1, required=False, allow_null=True)
    direccion_id = serializers.IntegerField(min_value=1, required=False, allow_null=True)
    metodo_pago = serializers.ChoiceField(choices=MetodoPago.choices)
    observaciones = serializers.CharField(
        max_length=200, required=False, allow_blank=True, default=""
    )
    items = ItemCarritoSerializer(many=True, allow_empty=False, max_length=50)
    # HU-61: the operator accepts to create the order when the sede has no capacity slot
    confirmar_sin_franja = serializers.BooleanField(required=False, default=False)

    def validate(self, attrs):
        origen = attrs.get("origen")
        direccion_id = attrs.get("direccion_id")

        if origen == OrigenPedido.TELEFONICO and not direccion_id:
            raise serializers.ValidationError(
                {"direccion_id": "Un pedido telefónico requiere indicar la dirección de entrega."}
            )

        return attrs