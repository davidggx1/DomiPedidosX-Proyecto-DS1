from rest_framework import serializers

from .models import MetodoPago


class AdicionItemSerializer(serializers.Serializer):
    adicion_id = serializers.IntegerField(min_value=1)
    cantidad = serializers.IntegerField(min_value=1, default=1)


class ItemCarritoSerializer(serializers.Serializer):
    producto_id = serializers.IntegerField(min_value=1, required=False)
    combo_id = serializers.IntegerField(min_value=1, required=False)
    tamano_id = serializers.IntegerField(min_value=1, required=False)
    cantidad = serializers.IntegerField(min_value=1, max_value=50)
    adiciones = AdicionItemSerializer(many=True, required=False)
    exclusiones = serializers.ListField(
        child=serializers.IntegerField(min_value=1), required=False
    )
    observaciones = serializers.CharField(
        max_length=300, required=False, allow_blank=True, default=""
    )

    def validate(self, attrs):
        producto, combo = attrs.get("producto_id"), attrs.get("combo_id")
        if bool(producto) == bool(combo):
            raise serializers.ValidationError(
                "Cada ítem debe traer producto_id o combo_id, pero no ambos."
            )
        if combo and (
            attrs.get("tamano_id") or attrs.get("adiciones") or attrs.get("exclusiones")
        ):
            raise serializers.ValidationError(
                "Un combo no admite tamaño, adiciones ni exclusiones."
            )
        ids = [a["adicion_id"] for a in attrs.get("adiciones", [])]
        if len(ids) != len(set(ids)):
            raise serializers.ValidationError("Hay adiciones repetidas en un ítem.")
        excl = attrs.get("exclusiones", [])
        if len(excl) != len(set(excl)):
            raise serializers.ValidationError("Hay exclusiones repetidas en un ítem.")
        return attrs


class ConfirmarPedidoSerializer(serializers.Serializer):
    sede_id = serializers.IntegerField(min_value=1)
    direccion_id = serializers.IntegerField(min_value=1)
    metodo_pago = serializers.ChoiceField(choices=MetodoPago.choices)
    observaciones = serializers.CharField(
        max_length=200, required=False, allow_blank=True, default=""
    )
    items = ItemCarritoSerializer(many=True, allow_empty=False, max_length=50)