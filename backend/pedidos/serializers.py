from rest_framework import serializers

from .estados import siguientes_estados
from .models import DetallePedido, DetallePedidoAdicion, EstadoPedido, HistorialEstadoPedido, Pedido


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


# --- Cocina: tablero Kanban (HU-29) y detalle de la comanda (HU-30) --------------


def nombre_linea(detalle):
    """'Hamburguesa clásica (Mediana)' o el nombre del combo."""
    if detalle.combo_id:
        return detalle.combo.nombre
    nombre = detalle.producto.nombre
    if detalle.producto_tamano_id:
        nombre += f" ({detalle.producto_tamano.nombre})"
    return nombre


class TarjetaCocinaSerializer(serializers.ModelSerializer):
    """
    Tarjeta resumida del tablero (HU-29, criterio 4): número, qué preparar y hora.
    `recibido_en` es cuando entró a cocina; `listo_en`, cuando quedó listo. Sirven
    para el cronómetro de HU-32, que se detiene al llegar a "listo para despacho".
    """

    recibido_en = serializers.DateTimeField(read_only=True)
    listo_en = serializers.DateTimeField(read_only=True, allow_null=True)
    resumen = serializers.SerializerMethodField()
    tiene_notas = serializers.SerializerMethodField()
    tiene_cambios = serializers.SerializerMethodField()
    siguientes_estados = serializers.SerializerMethodField()

    class Meta:
        model = Pedido
        fields = [
            "id",
            "numero_pedido",
            "estado",
            "recibido_en",
            "listo_en",
            "resumen",
            "tiene_notas",
            "tiene_cambios",
            "siguientes_estados",
        ]

    def get_resumen(self, pedido) -> list[str]:
        return [f"{d.cantidad}x {nombre_linea(d)}" for d in pedido.detalles.all()]

    def get_tiene_notas(self, pedido) -> bool:
        return bool(pedido.descripcion.strip()) or any(d.observaciones.strip() for d in pedido.detalles.all())

    def get_tiene_cambios(self, pedido) -> bool:
        """True si algún plato lleva adiciones o ingredientes quitados (para resaltar la tarjeta)."""
        return any(d.adiciones.all() or d.exclusiones.all() for d in pedido.detalles.all())

    def get_siguientes_estados(self, pedido) -> list[str]:
        return siguientes_estados(pedido.estado, self.context.get("rol"))


class AdicionComandaSerializer(serializers.ModelSerializer):
    nombre = serializers.CharField(source="adicion.nombre", read_only=True)

    class Meta:
        model = DetallePedidoAdicion
        fields = ["nombre", "cantidad"]


class LineaComandaSerializer(serializers.ModelSerializer):
    nombre = serializers.SerializerMethodField()
    tamano = serializers.CharField(source="producto_tamano.nombre", read_only=True, default=None)
    adiciones = AdicionComandaSerializer(many=True, read_only=True)
    sin = serializers.SerializerMethodField()

    class Meta:
        model = DetallePedido
        fields = ["id", "nombre", "tamano", "cantidad", "adiciones", "sin", "observaciones"]

    def get_nombre(self, detalle) -> str:
        if detalle.combo_id:
            return detalle.combo.nombre
        return detalle.producto.nombre

    def get_sin(self, detalle) -> list[str]:
        """Ingredientes que el cliente pidió quitar (cocina los muestra en rojo)."""
        return [exclusion.nombre_insumo for exclusion in detalle.exclusiones.all()]


class ComandaCocinaSerializer(TarjetaCocinaSerializer):
    """Detalle completo para preparar el pedido (HU-30)."""

    estado_nombre = serializers.CharField(source="get_estado_display", read_only=True)
    notas = serializers.CharField(source="descripcion", read_only=True)
    lineas = LineaComandaSerializer(source="detalles", many=True, read_only=True)

    class Meta(TarjetaCocinaSerializer.Meta):
        fields = [
            "id",
            "numero_pedido",
            "estado",
            "estado_nombre",
            "recibido_en",
            "listo_en",
            "notas",
            "lineas",
            "siguientes_estados",
        ]


# --- Despacho: asignación manual de repartidor (HU-35) ---------------------------


class AsignarRepartidorSerializer(serializers.Serializer):
    repartidor = serializers.IntegerField(
        min_value=1,
        error_messages={
            "required": "Selecciona un repartidor.",
            "invalid": "El repartidor debe indicarse con su id.",
            "min_value": "El repartidor debe indicarse con su id.",
        },
    )


class RepartidorAsignadoSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    nombre = serializers.SerializerMethodField()

    def get_nombre(self, repartidor) -> str:
        return f"{repartidor.empleado.nombres} {repartidor.empleado.apellidos}"


class PedidoDespachoSerializer(serializers.ModelSerializer):
    """Pedido listo para despacho, con su repartidor si ya tiene uno (HU-35, criterio 1)."""

    listo_en = serializers.DateTimeField(read_only=True, allow_null=True)
    resumen = serializers.SerializerMethodField()
    repartidor = RepartidorAsignadoSerializer(read_only=True, allow_null=True)

    class Meta:
        model = Pedido
        fields = [
            "id",
            "numero_pedido",
            "origen",
            "listo_en",
            "entrega_direccion",
            "entrega_barrio",
            "resumen",
            "repartidor",
        ]

    def get_resumen(self, pedido) -> list[str]:
        return [f"{d.cantidad}x {nombre_linea(d)}" for d in pedido.detalles.all()]
