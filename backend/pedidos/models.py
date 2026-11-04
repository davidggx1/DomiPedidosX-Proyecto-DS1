"""
Pedidos, detalles, historial de estados, facturación, consumo de cupos y notificaciones.
Depende de: usuarios, sedes, menu, promociones.
"""
from django.conf import settings
from django.db import models
from django.db.models import Q


class MetodoPago(models.TextChoices):
    EFECTIVO = "efectivo", "Efectivo"
    TARJETA = "tarjeta", "Tarjeta"
    TRANSFERENCIA = "transferencia", "Transferencia"


# Estados según el enunciado (4.4). Los usan Pedido y HistorialEstadoPedido.
class EstadoPedido(models.TextChoices):
    RECIBIDO = "recibido", "Recibido"
    EN_PREPARACION = "en_preparacion", "En preparación"
    LISTO_DESPACHO = "listo_despacho", "Listo para despacho"
    EN_CAMINO = "en_camino", "En camino"
    ENTREGADO = "entregado", "Entregado"
    CANCELADO = "cancelado", "Cancelado"


class OrigenPedido(models.TextChoices):
    WEB = "web", "Web"
    TELEFONICO = "telefonico", "Telefónico"
    MOSTRADOR = "mostrador", "Mostrador"


class EstadoFactura(models.TextChoices):
    PAGADA = "PAGADA", "Pagada"
    PENDIENTE = "PENDIENTE", "Pendiente"
    ANULADA = "ANULADA", "Anulada"


class TipoNotificacion(models.TextChoices):
    PEDIDO_CONFIRMADO = "pedido_confirmado", "Pedido confirmado"
    CAMBIO_ESTADO = "cambio_estado", "Cambio de estado"
    PEDIDO_CANCELADO = "pedido_cancelado", "Pedido cancelado"
    REPARTIDOR_ASIGNADO = "repartidor_asignado", "Repartidor asignado"
    PEDIDO_EN_CAMINO = "pedido_en_camino", "Pedido en camino"
    ALERTA_CAPACIDAD = "alerta_capacidad", "Alerta de capacidad"
    ALERTA_STOCK = "alerta_stock", "Alerta de stock bajo"


# Pedido NO guarda dinero: subtotal, domicilio, descuento, total y método de
# pago viven en Factura. El carrito se calcula desde DetallePedido.
class Pedido(models.Model):
    numero_pedido = models.CharField(max_length=20, unique=True)
    sede = models.ForeignKey(
        "sedes.Sede",
        on_delete=models.PROTECT,
        related_name="pedidos",
    )
    # Nullable: pedidos de mostrador sin cliente registrado.
    cliente = models.ForeignKey(
        "usuarios.Cliente",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="pedidos",
    )
    # Operador que creó el pedido (telefónico o mostrador).
    empleado = models.ForeignKey(
        "usuarios.Empleado",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="pedidos_creados",
    )
    # Nullable: pedidos de mostrador no tienen dirección.
    direccion_entrega = models.ForeignKey(
        "usuarios.DireccionEntrega",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="pedidos",
    )
    # Copia de la dirección al momento del pedido (HU-06): si el cliente luego
    # edita o elimina la dirección, el pedido conserva a dónde se entregó.
    entrega_alias = models.CharField(max_length=50, blank=True)
    entrega_direccion = models.CharField(max_length=255, blank=True)
    entrega_barrio = models.CharField(max_length=50, blank=True)
    entrega_latitud = models.FloatField(null=True, blank=True)
    entrega_longitud = models.FloatField(null=True, blank=True)
    # Zona usada al validar la cobertura (tarifa, mínimo, reportes por zona).
    zona_cobertura = models.ForeignKey(
        "sedes.ZonaCobertura",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="pedidos",
    )
    repartidor = models.ForeignKey(
        "usuarios.Repartidor",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="pedidos_asignados",
    )
    origen = models.CharField(
        max_length=20,
        choices=OrigenPedido.choices,
        default=OrigenPedido.WEB,
    )
    estado = models.CharField(
        max_length=20,
        choices=EstadoPedido.choices,
        default=EstadoPedido.RECIBIDO,
    )
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    # Minutos.
    tiempo_estimado_entrega = models.PositiveIntegerField(null=True, blank=True)
    motivo_cancelacion = models.TextField(blank=True)
    descripcion = models.CharField(max_length=200, blank=True)

    def asignar_direccion_entrega(self, direccion):
        """Liga la dirección y copia sus datos al pedido (no guarda)."""
        self.direccion_entrega = direccion
        self.entrega_alias = direccion.alias
        self.entrega_direccion = direccion.direccion
        self.entrega_barrio = direccion.barrio
        self.entrega_latitud = direccion.latitud
        self.entrega_longitud = direccion.longitud

    def __str__(self):
        return f"Pedido {self.numero_pedido}"


class DetallePedido(models.Model):
    pedido = models.ForeignKey(
        Pedido,
        on_delete=models.PROTECT,
        related_name="detalles",
    )
    producto = models.ForeignKey(
        "menu.Producto",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="detalles_pedido",
    )
    combo = models.ForeignKey(
        "promociones.Combo",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="detalles_pedido",
    )
    producto_tamano = models.ForeignKey(
        "menu.ProductoTamano",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="detalles_pedido",
    )
    cantidad = models.PositiveIntegerField()
    # Precio al momento de la compra (no cambia si luego sube el precio).
    precio_unitario = models.DecimalField(max_digits=10, decimal_places=2)
    subtotal = models.DecimalField(max_digits=12, decimal_places=2)
    observaciones = models.CharField(max_length=300, blank=True)

    # Una sola Meta con todas las restricciones.
    class Meta:
        constraints = [
            # XOR: producto o combo, nunca ambos ni ninguno.
            models.CheckConstraint(
                condition=(
                    (Q(producto__isnull=False) & Q(combo__isnull=True))
                    | (Q(producto__isnull=True) & Q(combo__isnull=False))
                ),
                name="detalle_pedido_producto_o_combo",
            ),
            # El tamaño solo aplica a productos, no a combos.
            models.CheckConstraint(
                condition=(
                    Q(producto__isnull=False) | Q(producto_tamano__isnull=True)
                ),
                name="detalle_tamano_solo_producto",
            ),
            models.CheckConstraint(
                condition=Q(cantidad__gt=0),
                name="detalle_pedido_cantidad_positiva",
            ),
            models.CheckConstraint(
                condition=Q(precio_unitario__gte=0),
                name="detalle_pedido_precio_no_negativo",
            ),
            models.CheckConstraint(
                condition=Q(subtotal__gte=0),
                name="detalle_pedido_subtotal_no_negativo",
            ),
        ]

    def __str__(self):
        return f"Detalle #{self.pk} del pedido #{self.pedido_id}"


class DetallePedidoAdicion(models.Model):
    detalle_pedido = models.ForeignKey(
        DetallePedido,
        on_delete=models.PROTECT,
        related_name="adiciones",
    )
    adicion = models.ForeignKey(
        "menu.Adicion",
        on_delete=models.PROTECT,
        related_name="detalles_pedido",
    )
    cantidad = models.PositiveIntegerField(default=1)
    precio_unitario = models.DecimalField(max_digits=10, decimal_places=2)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["detalle_pedido", "adicion"],
                name="detalle_adicion_unica",
            ),
            models.CheckConstraint(
                condition=Q(cantidad__gt=0),
                name="detalle_adicion_cantidad_positiva",
            ),
            models.CheckConstraint(
                condition=Q(precio_unitario__gte=0),
                name="detalle_adicion_precio_no_negativo",
            ),
        ]

    def __str__(self):
        return f"{self.adicion.nombre} - Detalle {self.detalle_pedido_id}"


class HistorialEstadoPedido(models.Model):
    pedido = models.ForeignKey(
        Pedido,
        on_delete=models.PROTECT,
        related_name="historial_estados",
    )
    # Nullable: los cambios automáticos del sistema no tienen usuario.
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="cambios_estado_pedido",
    )
    estado = models.CharField(
        max_length=20,
        choices=EstadoPedido.choices,
    )
    fecha_hora = models.DateTimeField(auto_now_add=True)
    observacion = models.TextField(blank=True)

    def __str__(self):
        return f"Pedido {self.pedido_id}: {self.estado}"


class Factura(models.Model):
    pedido = models.OneToOneField(
        Pedido,
        on_delete=models.PROTECT,
        related_name="factura",
    )
    numero = models.CharField(max_length=30, unique=True)
    fecha_emision = models.DateTimeField(auto_now_add=True)
    subtotal = models.DecimalField(max_digits=12, decimal_places=2)
    iva = models.DecimalField(max_digits=12, decimal_places=2)
    costo_domicilio = models.DecimalField(max_digits=12, decimal_places=2)
    valor_descuento = models.DecimalField(
        max_digits=12, decimal_places=2, default=0
    )
    total = models.DecimalField(max_digits=12, decimal_places=2)
    metodo_pago = models.CharField(
        max_length=20,
        choices=MetodoPago.choices,
    )
    estado_factura = models.CharField(
        max_length=20,
        choices=EstadoFactura.choices,
        default=EstadoFactura.PENDIENTE,
    )

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=Q(subtotal__gte=0),
                name="factura_subtotal_no_negativo",
            ),
            models.CheckConstraint(
                condition=Q(iva__gte=0),
                name="factura_iva_no_negativo",
            ),
            models.CheckConstraint(
                condition=Q(total__gte=0),
                name="factura_total_no_negativo",
            ),
            models.CheckConstraint(
                condition=Q(costo_domicilio__gte=0),
                name="factura_costo_domicilio_no_negativo",
            ),
            models.CheckConstraint(
                condition=Q(valor_descuento__gte=0),
                name="factura_valor_descuento_no_negativo",
            ),
        ]

    def __str__(self):
        return self.numero


# Un registro por pedido: da trazabilidad y permite devolver el cupo si el
# pedido se cancela. El cupo usado en un día se calcula sumando cantidad_usada
# por combo_sede y fecha (fecha_consumo).
class ConsumoCupoCombo(models.Model):
    combo_sede = models.ForeignKey(
        "promociones.ComboSede",
        on_delete=models.PROTECT,
        related_name="consumos_cupo",
    )
    pedido = models.ForeignKey(
        Pedido,
        on_delete=models.PROTECT,
        related_name="consumos_cupo_combo",
    )
    cantidad_usada = models.PositiveIntegerField(default=1)
    fecha_consumo = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=Q(cantidad_usada__gt=0),
                name="consumo_cupo_combo_cantidad_usada_positiva",
            ),
        ]

    def __str__(self):
        return (
            f"Consumo de {self.combo_sede.combo.nombre} "
            f"en pedido {self.pedido_id}"
        )


class Notificacion(models.Model):
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="notificaciones",
    )
    # Nullable: las alertas administrativas no están ligadas a un pedido.
    pedido = models.ForeignKey(
        Pedido,
        on_delete=models.SET_NULL,
        related_name="notificaciones",
        null=True,
        blank=True,
    )
    mensaje = models.TextField()
    tipo = models.CharField(
        max_length=30,
        choices=TipoNotificacion.choices,
    )
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    leida = models.BooleanField(default=False)

    def __str__(self):
        return f"Notificación {self.pk}"
