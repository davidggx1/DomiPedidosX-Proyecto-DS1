"""
Catálogo: categorías, productos, tamaños, insumos, adiciones y recetas.
No depende de otras apps del proyecto.
"""
import os
import uuid

from django.db import models
from django.db.models import Q


def ruta_imagen_producto(instance, filename):
    """Gives the image a random name so two files never overwrite each other"""
    extension = os.path.splitext(filename)[1].lower()
    return f"productos/{uuid.uuid4().hex}{extension}"


class CategoriaMenu(models.Model):
    nombre = models.CharField(max_length=50)
    descripcion = models.TextField(blank=True)
    activa = models.BooleanField(default=True)

    # Catálogo global único del restaurante.
    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["nombre"],
                name="categoria_menu_nombre_unico",
            ),
        ]

    def __str__(self):
        return self.nombre


class Producto(models.Model):
    class TipoControlStock(models.TextChoices):
        PRODUCTO = "PRODUCTO", "Producto terminado"
        INSUMOS = "INSUMOS", "Por insumos"
        NINGUNO = "NINGUNO", "Sin control"

    categoria = models.ForeignKey(
        CategoriaMenu,
        on_delete=models.PROTECT,
        related_name="productos",
    )
    nombre = models.CharField(max_length=100)
    descripcion = models.TextField(blank=True)
    imagen_url = models.URLField(max_length=500, blank=True)
    imagen = models.ImageField(upload_to=ruta_imagen_producto, blank=True)
    precio_base = models.DecimalField(max_digits=10, decimal_places=2)
    tiempo_preparacion = models.PositiveIntegerField()
    activo = models.BooleanField(default=True)
    tipo_control_stock = models.CharField(
        max_length=10,
        choices=TipoControlStock.choices,
        default=TipoControlStock.NINGUNO,
    )

    # El precio base puede ser 0 (productos promocionales gratuitos).
    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=Q(precio_base__gte=0),
                name="producto_precio_base_no_negativo",
            ),
        ]

    def __str__(self):
        return self.nombre


# precio_adicional es la DIFERENCIA sobre Producto.precio_base y puede ser
# negativo (tamaño más económico). Precio final = precio_base + precio_adicional.
# Que el precio final no sea < 0 se valida en el backend.
class ProductoTamano(models.Model):
    producto = models.ForeignKey(
        Producto,
        on_delete=models.PROTECT,
        related_name="tamanos",
    )
    nombre = models.CharField(max_length=30)
    precio_adicional = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
    )
    activo = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["producto", "nombre"],
                name="producto_tamano_nombre_unico",
            ),
        ]

    def __str__(self):
        return f"{self.producto.nombre} - {self.nombre}"


class Insumo(models.Model):
    class UnidadMedida(models.TextChoices):
        UNIDAD = "unidad", "Unidad"
        GRAMO = "g", "Gramo"
        KILOGRAMO = "kg", "Kilogramo"
        MILILITRO = "ml", "Mililitro"
        LITRO = "l", "Litro"

    nombre = models.CharField(max_length=100)
    unidad_medida = models.CharField(
        max_length=20,
        choices=UnidadMedida.choices,
    )
    activo = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["nombre"],
                name="insumo_nombre_unico",
            ),
        ]

    def __str__(self):
        return self.nombre


class Adicion(models.Model):
    # Insumo que consume la adición (queso extra -> queso).
    insumo = models.ForeignKey(
        Insumo,
        on_delete=models.PROTECT,
        related_name="adiciones",
    )
    nombre = models.CharField(max_length=80)
    descripcion = models.TextField(blank=True)
    imagen_url = models.URLField(max_length=500, blank=True)
    precio = models.DecimalField(max_digits=10, decimal_places=2)
    activa = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=Q(precio__gte=0),
                name="adicion_precio_no_negativo",
            ),
        ]

    def __str__(self):
        return self.nombre


class ProductoAdicion(models.Model):
    producto = models.ForeignKey(
        Producto,
        on_delete=models.PROTECT,
        related_name="adiciones_disponibles",
    )
    adicion = models.ForeignKey(
        Adicion,
        on_delete=models.PROTECT,
        related_name="productos",
    )
    max_cantidad = models.PositiveIntegerField(default=1)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["producto", "adicion"],
                name="producto_adicion_unica",
            ),
            models.CheckConstraint(
                condition=Q(max_cantidad__gte=1),
                name="producto_adicion_max_cantidad_positiva",
            ),
        ]

    def __str__(self):
        return f"{self.producto.nombre} - {self.adicion.nombre}"


class ProductoInsumo(models.Model):
    producto = models.ForeignKey(
        Producto,
        on_delete=models.PROTECT,
        related_name="insumos_requeridos",
    )
    insumo = models.ForeignKey(
        Insumo,
        on_delete=models.PROTECT,
        related_name="productos",
    )
    cantidad_necesaria = models.DecimalField(max_digits=12, decimal_places=3)
    es_excluible = models.BooleanField(default=False)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["producto", "insumo"],
                name="producto_insumo_unico",
            ),
            models.CheckConstraint(
                condition=Q(cantidad_necesaria__gt=0),
                name="producto_insumo_cantidad_positiva",
            ),
        ]

    def __str__(self):
        return f"{self.producto.nombre} - {self.insumo.nombre}"
