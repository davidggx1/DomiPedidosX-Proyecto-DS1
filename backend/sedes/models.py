"""
Ciudades, sedes, horarios, feriados, zonas de cobertura y capacidad.
No depende de otras apps del proyecto.
"""
from django.db import models
from django.db.models import Q


class DiaSemana(models.TextChoices):
    LUNES = "lunes", "Lunes"
    MARTES = "martes", "Martes"
    MIERCOLES = "miercoles", "Miércoles"
    JUEVES = "jueves", "Jueves"
    VIERNES = "viernes", "Viernes"
    SABADO = "sabado", "Sábado"
    DOMINGO = "domingo", "Domingo"


class Ciudad(models.Model):
    nombre = models.CharField(max_length=50)

    def __str__(self):
        return self.nombre


class Sede(models.Model):
    ciudad = models.ForeignKey(
        Ciudad,
        on_delete=models.PROTECT,
        related_name="sedes",
    )
    nombre = models.CharField(max_length=50, unique=True)
    direccion = models.CharField(max_length=255)
    activa = models.BooleanField(default=True)
    latitud = models.FloatField()
    longitud = models.FloatField()
    barrio = models.CharField(max_length=50)
    telefono = models.CharField(max_length=15)
    correo = models.EmailField()
    fecha_registro = models.DateField(auto_now_add=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=Q(latitud__gte=-90, latitud__lte=90),
                name="sede_latitud_valida",
            ),
            models.CheckConstraint(
                condition=Q(longitud__gte=-180, longitud__lte=180),
                name="sede_longitud_valida",
            ),
        ]

    def __str__(self):
        return self.nombre


class HorarioSede(models.Model):
    sede = models.ForeignKey(
        Sede,
        on_delete=models.PROTECT,
        related_name="horarios",
    )
    dia_semana = models.CharField(
        max_length=10,
        choices=DiaSemana.choices,
    )
    hora_apertura = models.TimeField()
    hora_cierre = models.TimeField()

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=Q(hora_apertura__lt=models.F("hora_cierre")),
                name="horario_sede_intervalo_valido",
            ),
            models.UniqueConstraint(
                fields=["sede", "dia_semana", "hora_apertura", "hora_cierre"],
                name="horario_sede_intervalo_unico",
            ),
        ]

    def __str__(self):
        return (
            f"{self.sede.nombre} - {self.get_dia_semana_display()}: "
            f"{self.hora_apertura} a {self.hora_cierre}"
        )


class Feriado(models.Model):
    sede = models.ForeignKey(
        Sede,
        on_delete=models.PROTECT,
        related_name="feriados",
    )
    fecha = models.DateField()
    descripcion = models.CharField(max_length=100)
    cerrado = models.BooleanField(default=True)
    hora_apertura = models.TimeField(null=True, blank=True)
    hora_cierre = models.TimeField(null=True, blank=True)

    # Cerrado no necesita horas; si abre, deben existir y cierre > apertura.
    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["sede", "fecha"],
                name="feriado_fecha_unica_por_sede",
            ),
            models.CheckConstraint(
                condition=(
                    Q(cerrado=True)
                    | (
                        Q(cerrado=False)
                        & Q(hora_apertura__isnull=False)
                        & Q(hora_cierre__isnull=False)
                        & Q(hora_apertura__lt=models.F("hora_cierre"))
                    )
                ),
                name="feriado_horario_especial_valido",
            ),
        ]

    def __str__(self):
        return f"{self.fecha} - {self.sede.nombre}"


class ZonaCobertura(models.Model):
    sede = models.ForeignKey(
        Sede,
        on_delete=models.PROTECT,
        related_name="zonas_cobertura",
    )
    nombre = models.CharField(max_length=50)
    # Unidad del radio: kilómetros.
    radio = models.FloatField()
    centro_latitud = models.FloatField()
    centro_longitud = models.FloatField()
    tarifa_domicilio = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True
    )
    # Minutos. Null = aún sin configurar (la zona queda desactivada).
    tiempo_estimado = models.IntegerField(null=True, blank=True)
    pedido_minimo = models.DecimalField(max_digits=10, decimal_places=2)
    activo = models.BooleanField(default=True)

    # Polígono opcional: lista de [latitud, longitud]. Si existe, la zona es por
    # polígono y centro_* y radio guardan el centro y el radio que lo envuelven
    # (los calcula el serializer). Si es null, la zona es circular.
    poligono_vertices = models.JSONField(null=True, blank=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=Q(radio__gt=0),
                name="zona_radio_positivo",
            ),
            models.CheckConstraint(
                condition=Q(centro_latitud__gte=-90, centro_latitud__lte=90),
                name="zona_latitud_valida",
            ),
            models.CheckConstraint(
                condition=Q(centro_longitud__gte=-180, centro_longitud__lte=180),
                name="zona_longitud_valida",
            ),
            models.CheckConstraint(
                condition=Q(tarifa_domicilio__gte=0),
                name="zona_tarifa_no_negativa",
            ),
            models.CheckConstraint(
                condition=Q(pedido_minimo__gte=0),
                name="zona_pedido_minimo_no_negativo",
            ),
            models.CheckConstraint(
                condition=Q(tiempo_estimado__gt=0),
                name="zona_tiempo_estimado_positivo",
            ),
            models.CheckConstraint(
                condition=(
                    Q(activo=False)
                    | (Q(tarifa_domicilio__isnull=False) & Q(tiempo_estimado__isnull=False))
                ),
                name="zona_activa_requiere_tarifa_y_tiempo",
            ),
        ]

    def __str__(self):
        return self.nombre


class CapacidadSede(models.Model):
    sede = models.ForeignKey(
        Sede,
        on_delete=models.PROTECT,
        related_name="capacidades",
    )
    hora_inicio = models.TimeField()
    hora_fin = models.TimeField()
    # Valores de DiaSemana separados por coma, p. ej. "lunes,martes,viernes".
    # Se valida en el backend (forms/serializers).
    dias_semana = models.CharField(max_length=60)
    max_pedidos_simultaneos = models.PositiveIntegerField()
    # Nº de pedidos simultáneos desde el cual se alerta al operador.
    umbral_alerta = models.PositiveIntegerField()

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=Q(hora_inicio__lt=models.F("hora_fin")),
                name="capacidad_intervalo_horario_valido",
            ),
            models.CheckConstraint(
                condition=Q(max_pedidos_simultaneos__gt=0),
                name="capacidad_pedidos_simultaneos_positiva",
            ),
            models.CheckConstraint(
                condition=Q(umbral_alerta__lte=models.F("max_pedidos_simultaneos")),
                name="capacidad_umbral_dentro_del_limite",
            ),
            models.UniqueConstraint(
                fields=["sede", "hora_inicio", "hora_fin", "dias_semana"],
                name="capacidad_intervalo_unico_por_sede",
            ),
        ]

    def __str__(self):
        return f"Capacidad de {self.sede.nombre}"


class EventoSede(models.TextChoices):
    """HU-83: avisos operativos de una sede a los que se puede suscribir."""

    STOCK_BAJO = "stock_bajo", "Alerta de stock bajo"
    CANCELACION = "cancelacion", "Pedido cancelado"
    SOBRECUPO = "sobrecupo", "Sobrecupo de capacidad"


class RolSuscrito(models.TextChoices):
    # Mismos valores que usuarios/roles.py (sedes no depende de usuarios).
    ADMINISTRADOR = "administrador", "Administradores"
    OPERADOR = "operador", "Operadores de la sede"
    COCINA = "cocina", "Cocina de la sede"
    REPARTIDOR = "repartidor", "Repartidores de la sede"


class SuscripcionNotificacion(models.Model):
    """
    HU-83: quién recibe por correo un evento de una sede.

    Cada fila es UN destinatario: un rol (todo el personal activo con ese rol en
    la sede; los administradores no tienen sede, así que son todos) o un correo
    suelto (p. ej. el del gerente). Nunca los dos a la vez.
    """

    sede = models.ForeignKey(
        Sede,
        on_delete=models.CASCADE,
        related_name="suscripciones",
    )
    evento = models.CharField(max_length=20, choices=EventoSede.choices)
    rol = models.CharField(max_length=20, choices=RolSuscrito.choices, blank=True, default="")
    correo = models.EmailField(blank=True, default="")
    creada_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["sede", "evento", "id"]
        constraints = [
            models.CheckConstraint(
                condition=(Q(rol="") & ~Q(correo="")) | (~Q(rol="") & Q(correo="")),
                name="suscripcion_rol_o_correo",
            ),
            models.UniqueConstraint(
                fields=["sede", "evento", "rol"],
                condition=~Q(rol=""),
                name="suscripcion_rol_unica",
            ),
            models.UniqueConstraint(
                fields=["sede", "evento", "correo"],
                condition=~Q(correo=""),
                name="suscripcion_correo_unica",
            ),
        ]

    def __str__(self):
        return f"{self.get_evento_display()} de {self.sede.nombre} → {self.rol or self.correo}"
