from rest_framework import serializers

from .estados import siguientes_estados
from .models import (
    DetallePedido,
    DetallePedidoAdicion,
    EstadoFactura,
    EstadoPedido,
    HistorialEstadoPedido,
    MetodoPago,
    Pedido,
)


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

def pedidos_con_detalle():
    return Pedido.objects.select_related("cliente", "factura").prefetch_related(
        "detalles__producto",
        "detalles__combo",
        "detalles__producto_tamano",
        "detalles__adiciones__adicion",
        "detalles__exclusiones",
    )


class PedidoEntranteSerializer(serializers.ModelSerializer):
    sede_id = serializers.IntegerField(read_only=True)
    cliente = serializers.SerializerMethodField()
    metodo_pago = serializers.SerializerMethodField()
    detalles = serializers.SerializerMethodField()

    class Meta:
        model = Pedido
        fields = [
            "id", "numero_pedido", "sede_id", "estado", "origen",
            "fecha_creacion", "descripcion", "tiempo_estimado_entrega",
            "cliente", "metodo_pago", "entrega_direccion", "entrega_barrio",
            "entrega_indicaciones", "detalles",
        ]

    def get_cliente(self, obj):
        if obj.cliente is None:
            return None
        return f"{obj.cliente.nombres} {obj.cliente.apellidos}"

    def get_metodo_pago(self, obj):
        factura = getattr(obj, "factura", None)
        return factura.metodo_pago if factura else None

    def get_detalles(self, obj):
        return [
            {
                "nombre": d.producto.nombre if d.producto_id else d.combo.nombre,
                "tamano": d.producto_tamano.nombre if d.producto_tamano_id else None,
                "cantidad": d.cantidad,
                "observaciones": d.observaciones,
                "adiciones": [
                    {"nombre": a.adicion.nombre, "cantidad": a.cantidad}
                    for a in d.adiciones.all()
                ],
                "sin": [e.nombre_insumo for e in d.exclusiones.all()],
            }
            for d in obj.detalles.all()
        ]


# --- Repartidor: mis entregas (HU-42) y detalle de la entrega (HU-43) ------------


def cobrar_en_efectivo(pedido):
    """True si el repartidor debe cobrar al entregar: paga en efectivo y no está pagada."""
    factura = getattr(pedido, "factura", None)
    return bool(
        factura
        and factura.metodo_pago == MetodoPago.EFECTIVO
        and factura.estado_factura == EstadoFactura.PENDIENTE
    )


class ClienteEntregaSerializer(serializers.Serializer):
    nombre = serializers.SerializerMethodField()
    celular = serializers.CharField(read_only=True)

    def get_nombre(self, cliente) -> str:
        return f"{cliente.nombres} {cliente.apellidos}"


class TarjetaEntregaSerializer(serializers.ModelSerializer):
    """Pedido en curso en la lista del repartidor (HU-42)."""

    estado_nombre = serializers.CharField(source="get_estado_display", read_only=True)
    cliente = ClienteEntregaSerializer(read_only=True, allow_null=True)
    total = serializers.DecimalField(
        source="factura.total", max_digits=12, decimal_places=2, read_only=True, default=None
    )
    metodo_pago = serializers.CharField(source="factura.metodo_pago", read_only=True, default=None)
    metodo_pago_nombre = serializers.CharField(
        source="factura.get_metodo_pago_display", read_only=True, default=None
    )
    cobrar_en_efectivo = serializers.SerializerMethodField()
    siguientes_estados = serializers.SerializerMethodField()

    class Meta:
        model = Pedido
        fields = [
            "id",
            "numero_pedido",
            "estado",
            "estado_nombre",
            "fecha_creacion",
            "entrega_direccion",
            "entrega_barrio",
            "cliente",
            "total",
            "metodo_pago",
            "metodo_pago_nombre",
            "cobrar_en_efectivo",
            "siguientes_estados",
        ]

    def get_cobrar_en_efectivo(self, pedido) -> bool:
        return cobrar_en_efectivo(pedido)

    def get_siguientes_estados(self, pedido) -> list[str]:
        return siguientes_estados(pedido.estado, self.context.get("rol"))


class DetalleEntregaSerializer(TarjetaEntregaSerializer):
    """Comanda de entrega: a dónde ir, qué llevar y cuánto cobrar (HU-43)."""

    notas = serializers.CharField(source="descripcion", read_only=True)
    lineas = LineaComandaSerializer(source="detalles", many=True, read_only=True)
    subtotal = serializers.DecimalField(
        source="factura.subtotal", max_digits=12, decimal_places=2, read_only=True, default=None
    )
    costo_domicilio = serializers.DecimalField(
        source="factura.costo_domicilio", max_digits=12, decimal_places=2, read_only=True, default=None
    )
    valor_descuento = serializers.DecimalField(
        source="factura.valor_descuento", max_digits=12, decimal_places=2, read_only=True, default=None
    )

    class Meta(TarjetaEntregaSerializer.Meta):
        fields = TarjetaEntregaSerializer.Meta.fields + [
            "entrega_alias",
            "entrega_indicaciones",
            "entrega_latitud",
            "entrega_longitud",
            "notas",
            "lineas",
            "subtotal",
            "costo_domicilio",
            "valor_descuento",
        ]
