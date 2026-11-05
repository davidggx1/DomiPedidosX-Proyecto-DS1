from rest_framework import serializers

from .estados import siguientes_estados
from .models import EstadoPedido, HistorialEstadoPedido, Pedido


class CambioEstadoSerializer(serializers.Serializer):
    """Datos para cambiar el estado de un pedido (HU-31)."""

    estado = serializers.ChoiceField(
        choices=EstadoPedido.choices,
        error_messages={
            "required": "Indica el nuevo estado.",
            "invalid_choice": "El estado indicado no existe.",
        },
    )
    motivo = serializers.CharField(required=False, allow_blank=True, max_length=500)


class HistorialEstadoSerializer(serializers.ModelSerializer):
    estado_nombre = serializers.CharField(source="get_estado_display", read_only=True)
    usuario = serializers.EmailField(source="usuario.email", read_only=True, default=None)

    class Meta:
        model = HistorialEstadoPedido
        fields = ["estado", "estado_nombre", "fecha_hora", "usuario", "observacion"]


class EstadoPedidoSerializer(serializers.ModelSerializer):
    """Estado actual, historial con hora de cada paso y a qué estados puede pasar quien consulta."""

    estado_nombre = serializers.CharField(source="get_estado_display", read_only=True)
    historial = HistorialEstadoSerializer(source="historial_estados", many=True, read_only=True)
    siguientes_estados = serializers.SerializerMethodField()

    class Meta:
        model = Pedido
        fields = [
            "id",
            "numero_pedido",
            "estado",
            "estado_nombre",
            "motivo_cancelacion",
            "historial",
            "siguientes_estados",
        ]

    def get_siguientes_estados(self, pedido) -> list[str]:
        return siguientes_estados(pedido.estado, self.context.get("rol"))
