"""
Usuario (autenticación por correo), perfiles de cliente, empleado y repartidor,
y direcciones de entrega.
Depende de: sedes.
"""
from django.contrib.auth.models import AbstractUser
from django.core.validators import RegexValidator
from django.db import models
from django.db.models import Q

# Validador de 10 dígitos numéricos exactos para HU-02
validator_telefono = RegexValidator(
    regex=r"^\d{10}$",
    message="El número de teléfono celular debe contener exactamente 10 dígitos numéricos.",
)

class TipoDocumento(models.TextChoices):
    CC = "CC", "Cédula de ciudadanía (C.C.)"
    TI = "TI", "Tarjeta de identidad (T.I.)"
    CE = "CE", "Cédula de extranjería (C.E.)"
    PA = "PA", "Pasaporte"
    RC = "RC", "Registro civil"
    PPT = "PPT", "Permiso por Protección Temporal (PPT)"


# AbstractUser ya aporta contraseña con hash, activación, permisos, grupos
# y recuperación de acceso. Los roles (cliente, operador, cocina, repartidor,
# administrador) se manejan con grupos y permisos de Django.
class Usuario(AbstractUser):
    email = models.EmailField(
        unique=True,
        verbose_name="correo electrónico",
    )

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["username"]

    def __str__(self):
        return self.email


class Cliente(models.Model):
    usuario = models.OneToOneField(
        Usuario,
        on_delete=models.PROTECT,
        related_name="cliente",
    )
    tipo_documento = models.CharField(
        max_length=3,
        choices=TipoDocumento.choices,
    )
    num_documento = models.CharField(max_length=12)
    nombres = models.CharField(max_length=100)
    apellidos = models.CharField(max_length=100)
    celular = models.CharField(
        max_length=10,
        unique=True,
        validators=[validator_telefono],
        help_text="Número celular de 10 dígitos numéricos.",
    )
    fecha_nacimiento = models.DateField()

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["tipo_documento", "num_documento"],
                name="cliente_documento_unico",
            ),
        ]

    def __str__(self):
        return f"{self.nombres} {self.apellidos}"


class Empleado(models.Model):
    usuario = models.OneToOneField(
        Usuario,
        on_delete=models.PROTECT,
        related_name="empleado",
    )
    sede = models.ForeignKey(
        "sedes.Sede",
        on_delete=models.PROTECT,
        related_name="empleados",
        null=True,  # Permite None únicamente si es Administrador
        blank=True,
    )
    tipo_documento = models.CharField(
        max_length=3,
        choices=TipoDocumento.choices,
    )
    num_documento = models.CharField(max_length=12)
    nombres = models.CharField(max_length=100)
    apellidos = models.CharField(max_length=100)
    celular = models.CharField(max_length=15)
    direccion = models.CharField(max_length=255)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["tipo_documento", "num_documento"],
                name="empleado_documento_unico",
            ),
        ]

    def __str__(self):
        return f"{self.nombres} {self.apellidos}"


class Repartidor(models.Model):
    empleado = models.OneToOneField(
        Empleado,
        on_delete=models.PROTECT,
        related_name="perfil_repartidor",
    )
    disponible = models.BooleanField(default=True)
    # La ubicación en el mapa es opcional.
    latitud = models.FloatField(null=True, blank=True)
    longitud = models.FloatField(null=True, blank=True)

    def __str__(self):
        return f"Repartidor: {self.empleado.nombres} {self.empleado.apellidos}"


# La zona de cobertura ya NO va aquí: se valida al hacer el pedido y se
# guarda en Pedido.zona_cobertura.
class DireccionEntrega(models.Model):
    ciudad = models.ForeignKey(
        "sedes.Ciudad",
        on_delete=models.PROTECT,
        related_name="direcciones_entrega",
    )
    cliente = models.ForeignKey(
        Cliente,
        on_delete=models.PROTECT,
        related_name="direcciones_entrega",
    )
    # Nombre corto para reconocerla (HU-06): "Casa", "Oficina"...
    alias = models.CharField(max_length=50, blank=True, default="")
    direccion = models.CharField(max_length=255)
    latitud = models.FloatField()
    longitud = models.FloatField()
    barrio = models.CharField(max_length=50, blank=True)
    es_principal = models.BooleanField(default=False)
    # Borrado lógico: los pedidos anteriores siguen apuntando a la dirección.
    activa = models.BooleanField(default=True)

    class Meta:
        constraints = [
            # Varias direcciones por cliente, pero máximo una principal.
            models.UniqueConstraint(
                fields=["cliente"],
                condition=Q(es_principal=True),
                name="una_direccion_principal_por_cliente",
            ),
            models.CheckConstraint(
                condition=Q(latitud__gte=-90, latitud__lte=90),
                name="direccion_latitud_valida",
            ),
            models.CheckConstraint(
                condition=Q(longitud__gte=-180, longitud__lte=180),
                name="direccion_longitud_valida",
            ),
        ]

    def __str__(self):
        return self.direccion
