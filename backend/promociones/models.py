"""
Promociones, combos, productos incluidos y su disponibilidad/cupo por sede.
Depende de: menu, sedes.
"""
from django.db import models
from django.db.models import Q
from django.utils import timezone


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


# --- HU-84 · Promociones ----------------------------------------------------------


class TipoDescuento(models.TextChoices):
    PORCENTAJE = "porcentaje", "Porcentaje"
    VALOR_FIJO = "valor_fijo", "Valor fijo"


class EstadoPromocion(models.TextChoices):
    VIGENTE = "vigente", "Vigente"
    PROGRAMADA = "programada", "Programada"
    VENCIDA = "vencida", "Vencida"
    INACTIVA = "inactiva", "Inactiva"


class PromocionQuerySet(models.QuerySet):
    def utilizables(self, hoy=None):
        """Las únicas que se pueden aplicar a una compra: activas y dentro de su vigencia."""
        hoy = hoy or timezone.localdate()
        return self.filter(activa=True, fecha_inicio__lte=hoy, fecha_fin__gte=hoy)

    def con_estado(self, estado, hoy=None):
        hoy = hoy or timezone.localdate()
        if estado == EstadoPromocion.INACTIVA:
            return self.filter(activa=False)
        activas = self.filter(activa=True)
        if estado == EstadoPromocion.VIGENTE:
            return activas.filter(fecha_inicio__lte=hoy, fecha_fin__gte=hoy)
        if estado == EstadoPromocion.PROGRAMADA:
            return activas.filter(fecha_inicio__gt=hoy)
        if estado == EstadoPromocion.VENCIDA:
            return activas.filter(fecha_fin__lt=hoy)
        return self.none()


class Promocion(models.Model):
    sede = models.ForeignKey(
        "sedes.Sede",
        on_delete=models.PROTECT,
        related_name="promociones",
    )
    nombre = models.CharField(max_length=100)
    descripcion = models.TextField(blank=True)
    tipo_descuento = models.CharField(max_length=12, choices=TipoDescuento.choices)
    # Porcentaje (0 a 100) o valor fijo en pesos, según tipo_descuento.
    valor = models.DecimalField(max_digits=10, decimal_places=2)
    # Vigencia: ambas fechas incluidas.
    fecha_inicio = models.DateField()
    fecha_fin = models.DateField()
    condiciones = models.TextField(blank=True)
    # Borrado lógico: una promoción desactivada no se usa, pero su historial se conserva.
    activa = models.BooleanField(default=True)
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    objects = PromocionQuerySet.as_manager()

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=Q(valor__gt=0),
                name="promocion_descuento_positivo",
            ),
            models.CheckConstraint(
                condition=Q(tipo_descuento="valor_fijo") | Q(valor__lte=100),
                name="promocion_porcentaje_maximo_100",
            ),
            models.CheckConstraint(
                condition=Q(fecha_inicio__lte=models.F("fecha_fin")),
                name="promocion_vigencia_valida",
            ),
        ]

    def estado(self, hoy=None):
        hoy = hoy or timezone.localdate()
        if not self.activa:
            return EstadoPromocion.INACTIVA
        if hoy < self.fecha_inicio:
            return EstadoPromocion.PROGRAMADA
        if hoy > self.fecha_fin:
            return EstadoPromocion.VENCIDA
        return EstadoPromocion.VIGENTE

    def utilizable(self, hoy=None):
        return self.estado(hoy) == EstadoPromocion.VIGENTE

    def __str__(self):
        return f"{self.nombre} - {self.sede.nombre}"