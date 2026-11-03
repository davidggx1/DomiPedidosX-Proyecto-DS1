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
