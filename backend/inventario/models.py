"""
Existencias y disponibilidad por sede (productos e insumos).
Depende de: menu, sedes.
"""
from django.db import models
from django.db.models import Q


class InventarioProducto(models.Model):
    sede = models.ForeignKey(
        "sedes.Sede",
        on_delete=models.PROTECT,
        related_name="inventario_productos",
    )
    producto = models.ForeignKey(
        "menu.Producto",
        on_delete=models.PROTECT,
        related_name="inventarios",
    )
    stock_actual = models.PositiveIntegerField(default=0)
    stock_minimo = models.PositiveIntegerField(default=0)
    disponible = models.BooleanField(default=True)
    demanda_diaria = models.PositiveIntegerField(default=0)
    fecha_actualizacion = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["sede", "producto"],
                name="inventario_producto_sede_unico",
            ),
        ]

    def __str__(self):
        return f"{self.producto.nombre} - {self.sede.nombre}"


# Los insumos se miden en kg, litros, etc., por eso las cantidades son
# decimales (igual que ProductoInsumo.cantidad_necesaria).
# El descuento automático de insumos al preparar un pedido se implementa
# en la lógica del flujo de pedidos, no en los modelos.
class InventarioInsumo(models.Model):
    sede = models.ForeignKey(
        "sedes.Sede",
        on_delete=models.PROTECT,
        related_name="inventario_insumos",
    )
    insumo = models.ForeignKey(
        "menu.Insumo",
        on_delete=models.PROTECT,
        related_name="inventarios",
    )
    stock_actual = models.DecimalField(
        max_digits=12, decimal_places=3, default=0
    )
    stock_minimo = models.DecimalField(
        max_digits=12, decimal_places=3, default=0
    )
    disponible = models.BooleanField(default=True)
    demanda_diaria = models.DecimalField(
        max_digits=12, decimal_places=3, default=0
    )
    fecha_actualizacion = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["sede", "insumo"],
                name="inventario_insumo_sede_unico",
            ),
            models.CheckConstraint(
                condition=Q(stock_actual__gte=0),
                name="inventario_insumo_stock_actual_no_negativo",
            ),
            models.CheckConstraint(
                condition=Q(stock_minimo__gte=0),
                name="inventario_insumo_stock_minimo_no_negativo",
            ),
            models.CheckConstraint(
                condition=Q(demanda_diaria__gte=0),
                name="inventario_insumo_demanda_no_negativa",
            ),
        ]

    def __str__(self):
        return f"{self.insumo.nombre} - {self.sede.nombre}"


class AlertaInventario(models.Model):
    """
    Low stock alert (HU-16). While the stock of an item in a sede is at or under
    its minimum there is exactly ONE active alert for it (the database enforces
    it). When the stock goes over the minimum the alert is marked as resolved
    """

    class Estado(models.TextChoices):
        ACTIVA = "activa", "Activa"
        RESUELTA = "resuelta", "Resuelta"

    sede = models.ForeignKey(
        "sedes.Sede",
        on_delete=models.CASCADE,
        related_name="alertas_inventario",
    )
    # exactly one of producto / insumo is set
    producto = models.ForeignKey(
        "menu.Producto",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="alertas_inventario",
    )
    insumo = models.ForeignKey(
        "menu.Insumo",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="alertas_inventario",
    )
    estado = models.CharField(
        max_length=10, choices=Estado.choices, default=Estado.ACTIVA
    )
    stock_al_disparar = models.DecimalField(max_digits=12, decimal_places=3)
    stock_minimo_al_disparar = models.DecimalField(max_digits=12, decimal_places=3)
    creada_en = models.DateTimeField(auto_now_add=True)
    resuelta_en = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-creada_en", "-id"]
        constraints = [
            models.CheckConstraint(
                condition=(
                    Q(producto__isnull=False, insumo__isnull=True)
                    | Q(producto__isnull=True, insumo__isnull=False)
                ),
                name="alerta_inventario_un_solo_item",
            ),
            models.UniqueConstraint(
                fields=["sede", "producto"],
                condition=Q(estado="activa", producto__isnull=False),
                name="alerta_activa_producto_unica",
            ),
            models.UniqueConstraint(
                fields=["sede", "insumo"],
                condition=Q(estado="activa", insumo__isnull=False),
                name="alerta_activa_insumo_unica",
            ),
        ]

    def __str__(self):
        item = self.producto or self.insumo
        return f"Alerta {self.estado}: {item} - {self.sede}"
