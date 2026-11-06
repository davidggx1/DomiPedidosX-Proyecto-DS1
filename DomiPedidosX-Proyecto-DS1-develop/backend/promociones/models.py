"""
Combos, productos incluidos y su disponibilidad/cupo por sede.
Depende de: menu, sedes.
"""
from django.db import models
from django.db.models import Q


class Combo(models.Model):
    nombre = models.CharField(max_length=100)
    condicion = models.TextField(blank=True)
    descripcion = models.TextField(blank=True)
    precio = models.DecimalField(max_digits=10, decimal_places=2)
    activo = models.BooleanField(default=True)
    fecha_inicio = models.DateField()
    fecha_vencimiento = models.DateField()

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=Q(precio__gte=0),
                name="combo_precio_no_negativo",
            ),
            models.CheckConstraint(
                condition=Q(fecha_inicio__lte=models.F("fecha_vencimiento")),
                name="combo_vigencia_valida",
            ),
        ]

    def __str__(self):
        return self.nombre


class ComboProducto(models.Model):
    combo = models.ForeignKey(
        Combo,
        on_delete=models.PROTECT,
        related_name="productos_incluidos",
    )
    producto = models.ForeignKey(
        "menu.Producto",
        on_delete=models.PROTECT,
        related_name="combos",
    )
    cantidad = models.PositiveIntegerField(default=1)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["combo", "producto"],
                name="combo_producto_unico",
            ),
            models.CheckConstraint(
                condition=Q(cantidad__gt=0),
                name="combo_producto_cantidad_positiva",
            ),
        ]

    def __str__(self):
        return f"{self.combo.nombre} - {self.producto.nombre}"


class ComboSede(models.Model):
    combo = models.ForeignKey(
        Combo,
        on_delete=models.PROTECT,
        related_name="sedes_disponibles",
    )
    sede = models.ForeignKey(
        "sedes.Sede",
        on_delete=models.PROTECT,
        related_name="combos_disponibles",
    )
    activo = models.BooleanField(default=True)
    # NULL = sin cupo diario.
    cupo_max_diario = models.PositiveIntegerField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["combo", "sede"],
                name="combo_sede_unico",
            ),
            models.CheckConstraint(
                condition=Q(cupo_max_diario__isnull=True) | Q(cupo_max_diario__gt=0),
                name="combo_sede_cupo_positivo",
            ),
        ]

    def __str__(self):
        return f"{self.combo.nombre} - {self.sede.nombre}"
