from django.contrib.auth.models import AbstractUser
from django.db import models

#para la regla XOR de pedidos o combos, pero no ambos:
from django.db.models import Q


# ---------------------------------------------------------------------------
# Catálogos de opciones cerradas (TextChoices)
# ---------------------------------------------------------------------------

class TipoDocumento(models.TextChoices):
    CC = "CC", "Cédula de ciudadanía (C.C.)"
    TI = "TI", "Tarjeta de identidad (T.I.)"
    CE = "CE", "Cédula de extranjería (C.E.)"
    PA = "PA", "Pasaporte"
    RC = "RC", "Registro civil"
    PPT = "PPT", "Permiso por Protección Temporal (PPT)"


class MetodoPago(models.TextChoices):
    EFECTIVO = "efectivo", "Efectivo"
    TARJETA = "tarjeta", "Tarjeta"
    TRANSFERENCIA = "transferencia", "Transferencia"


class DiaSemana(models.TextChoices):
    LUNES = "lunes", "Lunes"
    MARTES = "martes", "Martes"
    MIERCOLES = "miercoles", "Miércoles"
    JUEVES = "jueves", "Jueves"
    VIERNES = "viernes", "Viernes"
    SABADO = "sabado", "Sábado"
    DOMINGO = "domingo", "Domingo"


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


# ---------------------------------------------------------------------------
# Usuarios
# ---------------------------------------------------------------------------

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


class Ciudad(models.Model):
    idCiudad = models.AutoField(primary_key=True)
    nombre = models.CharField(max_length=50)

    def __str__(self):
        return self.nombre


class Sede(models.Model):
    idSede = models.AutoField(primary_key=True)
    ciudad = models.ForeignKey(
        Ciudad,
        on_delete=models.PROTECT,
        related_name="sedes",
    )
    nombre = models.CharField(max_length=50)
    direccion = models.CharField(max_length=255)
    activa = models.BooleanField(default=True)
    latitud = models.FloatField()
    longitud = models.FloatField()
    barrio = models.CharField(max_length=50)
    telefono = models.CharField(max_length=15)
    correo = models.EmailField()
    fechaRegistro = models.DateField(auto_now_add=True)

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


class ZonaCobertura(models.Model):
    idZonaCobertura = models.AutoField(primary_key=True)
    sede = models.ForeignKey(
        Sede,
        on_delete=models.PROTECT,
        related_name="zonas_cobertura",
    )
    nombre = models.CharField(max_length=50)
    # Unidad del radio: kilómetros.
    radio = models.FloatField()
    centroLatitud = models.FloatField()
    centroLongitud = models.FloatField()
    tarifaDomicilio = models.DecimalField(max_digits=10, decimal_places=2)
    # Minutos.
    tiempoEstimado = models.IntegerField()
    pedidoMinimo = models.DecimalField(max_digits=10, decimal_places=2)
    activo = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=Q(radio__gt=0),
                name="zona_radio_positivo",
            ),
            models.CheckConstraint(
                condition=Q(centroLatitud__gte=-90, centroLatitud__lte=90),
                name="zona_latitud_valida",
            ),
            models.CheckConstraint(
                condition=Q(centroLongitud__gte=-180, centroLongitud__lte=180),
                name="zona_longitud_valida",
            ),
            models.CheckConstraint(
                condition=Q(tarifaDomicilio__gte=0),
                name="zona_tarifa_no_negativa",
            ),
            models.CheckConstraint(
                condition=Q(pedidoMinimo__gte=0),
                name="zona_pedido_minimo_no_negativo",
            ),
            models.CheckConstraint(
                condition=Q(tiempoEstimado__gt=0),
                name="zona_tiempo_estimado_positivo",
            ),
        ]

    def __str__(self):
        return self.nombre


class Cliente(models.Model):
    idCliente = models.AutoField(primary_key=True)
    usuario = models.OneToOneField(
        Usuario,
        on_delete=models.PROTECT,
        related_name="cliente",
    )
    tipoDocumento = models.CharField(
        max_length=3,
        choices=TipoDocumento.choices,
    )
    numDocumento = models.CharField(max_length=12)
    nombres = models.CharField(max_length=100)
    apellidos = models.CharField(max_length=100)
    celular = models.CharField(max_length=15)
    fechaNacimiento = models.DateField()

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["tipoDocumento", "numDocumento"],
                name="cliente_documento_unico",
            ),
        ]

    def __str__(self):
        return f"{self.nombres} {self.apellidos}"


class Empleado(models.Model):
    idEmpleado = models.AutoField(primary_key=True)
    usuario = models.OneToOneField(
        Usuario,
        on_delete=models.PROTECT,
        related_name="empleado",
    )
    sede = models.ForeignKey(
        Sede,
        on_delete=models.PROTECT,
        related_name="empleados",
    )
    tipoDocumento = models.CharField(
        max_length=3,
        choices=TipoDocumento.choices,
    )
    numDocumento = models.CharField(max_length=12)
    nombres = models.CharField(max_length=100)
    apellidos = models.CharField(max_length=100)
    celular = models.CharField(max_length=15)
    direccion = models.CharField(max_length=255)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["tipoDocumento", "numDocumento"],
                name="empleado_documento_unico",
            ),
        ]

    def __str__(self):
        return f"{self.nombres} {self.apellidos}"


# La zona de cobertura ya NO va aquí: se valida al hacer el pedido y se
# guarda en Pedido.zonaCobertura.
class DireccionEntrega(models.Model):
    idDireccionEntrega = models.AutoField(primary_key=True)
    ciudad = models.ForeignKey(
        Ciudad,
        on_delete=models.PROTECT,
        related_name="direcciones_entrega",
    )
    cliente = models.ForeignKey(
        Cliente,
        on_delete=models.PROTECT,
        related_name="direcciones_entrega",
    )
    direccion = models.CharField(max_length=255)
    latitud = models.FloatField()
    longitud = models.FloatField()
    barrio = models.CharField(max_length=50)
    esPrincipal = models.BooleanField(default=False)

    class Meta:
        constraints = [
            # Varias direcciones por cliente, pero máximo una principal.
            models.UniqueConstraint(
                fields=["cliente"],
                condition=Q(esPrincipal=True),
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


class Notificacion(models.Model):
    idNotificacion = models.AutoField(primary_key=True)
    usuario = models.ForeignKey(
        Usuario,
        on_delete=models.PROTECT,
        related_name="notificaciones",
    )
    # Nullable: las alertas administrativas no están ligadas a un pedido.
    pedido = models.ForeignKey(
        "Pedido",
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
    fechaCreacion = models.DateTimeField(auto_now_add=True)
    leida = models.BooleanField(default=False)

    def __str__(self):
        return f"Notificación {self.idNotificacion}"


# ---------------------------------------------------------------------------
# Capacidad, horarios y feriados
# ---------------------------------------------------------------------------

class CapacidadSede(models.Model):
    idCapacidadSede = models.AutoField(primary_key=True)
    sede = models.ForeignKey(
        Sede,
        on_delete=models.PROTECT,
        related_name="capacidades",
    )
    horaInicio = models.TimeField()
    horaFin = models.TimeField()
    # Valores de DiaSemana separados por coma, p. ej. "lunes,martes,viernes".
    # Se valida en el backend (forms/serializers).
    diasSemana = models.CharField(max_length=60)
    maxPedidosSimultaneos = models.PositiveIntegerField()
    # Nº de pedidos simultáneos desde el cual se alerta al operador.
    umbralAlerta = models.PositiveIntegerField()

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=Q(horaInicio__lt=models.F("horaFin")),
                name="capacidad_intervalo_horario_valido",
            ),
            models.CheckConstraint(
                condition=Q(maxPedidosSimultaneos__gt=0),
                name="capacidad_pedidos_simultaneos_positiva",
            ),
            models.CheckConstraint(
                condition=Q(umbralAlerta__lte=models.F("maxPedidosSimultaneos")),
                name="capacidad_umbral_dentro_del_limite",
            ),
            models.UniqueConstraint(
                fields=["sede", "horaInicio", "horaFin", "diasSemana"],
                name="capacidad_intervalo_unico_por_sede",
            ),
        ]

    def __str__(self):
        return f"Capacidad de {self.sede.nombre}"


class HorarioSede(models.Model):
    idHorarioSede = models.AutoField(primary_key=True)
    sede = models.ForeignKey(
        Sede,
        on_delete=models.PROTECT,
        related_name="horarios",
    )
    diaSemana = models.CharField(
        max_length=10,
        choices=DiaSemana.choices,
    )
    horaApertura = models.TimeField()
    horaCierre = models.TimeField()

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=Q(horaApertura__lt=models.F("horaCierre")),
                name="horario_sede_intervalo_valido",
            ),
            models.UniqueConstraint(
                fields=["sede", "diaSemana", "horaApertura", "horaCierre"],
                name="horario_sede_intervalo_unico",
            ),
        ]

    def __str__(self):
        return (
            f"{self.sede.nombre} - {self.get_diaSemana_display()}: "
            f"{self.horaApertura} a {self.horaCierre}"
        )


class Feriado(models.Model):
    idFeriado = models.AutoField(primary_key=True)
    sede = models.ForeignKey(
        Sede,
        on_delete=models.PROTECT,
        related_name="feriados",
    )
    fecha = models.DateField()
    descripcion = models.CharField(max_length=100)
    cerrado = models.BooleanField(default=True)
    horaApertura = models.TimeField(null=True, blank=True)
    horaCierre = models.TimeField(null=True, blank=True)

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
                        & Q(horaApertura__isnull=False)
                        & Q(horaCierre__isnull=False)
                        & Q(horaApertura__lt=models.F("horaCierre"))
                    )
                ),
                name="feriado_horario_especial_valido",
            ),
        ]

    def __str__(self):
        return f"{self.fecha} - {self.sede.nombre}"


# ---------------------------------------------------------------------------
# Menú, productos e inventario
# ---------------------------------------------------------------------------

class CategoriaMenu(models.Model):
    idCategoriaMenu = models.AutoField(primary_key=True)
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

    idProducto = models.AutoField(primary_key=True)
    categoria = models.ForeignKey(
        CategoriaMenu,
        on_delete=models.PROTECT,
        related_name="productos",
    )
    nombre = models.CharField(max_length=100)
    descripcion = models.TextField(blank=True)
    imagenUrl = models.URLField(max_length=500, blank=True)
    precioBase = models.DecimalField(max_digits=10, decimal_places=2)
    tiempoPreparacion = models.PositiveIntegerField()
    activo = models.BooleanField(default=True)
    tipoControlStock = models.CharField(
        max_length=10,
        choices=TipoControlStock.choices,
        default=TipoControlStock.NINGUNO,
    )

    # El precio base puede ser 0 (productos promocionales gratuitos).
    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=Q(precioBase__gte=0),
                name="producto_precio_base_no_negativo",
            ),
        ]

    def __str__(self):
        return self.nombre


# precioAdicional es la DIFERENCIA sobre Producto.precioBase y puede ser
# negativo (tamaño más económico). Precio final = precioBase + precioAdicional.
# Que el precio final no sea < 0 se valida en el backend.
class ProductoTamano(models.Model):
    idProductoTamano = models.AutoField(primary_key=True)
    producto = models.ForeignKey(
        Producto,
        on_delete=models.PROTECT,
        related_name="tamanos",
    )
    nombre = models.CharField(max_length=30)
    precioAdicional = models.DecimalField(
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

    idInsumo = models.AutoField(primary_key=True)
    nombre = models.CharField(max_length=100)
    unidadMedida = models.CharField(
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
    idAdicion = models.AutoField(primary_key=True)
    # Insumo que consume la adición (queso extra -> queso).
    insumo = models.ForeignKey(
        Insumo,
        on_delete=models.PROTECT,
        related_name="adiciones",
    )
    nombre = models.CharField(max_length=80)
    descripcion = models.TextField(blank=True)
    imagenUrl = models.URLField(max_length=500, blank=True)
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
    idProductoAdicion = models.AutoField(primary_key=True)
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
    maxCantidad = models.PositiveIntegerField(default=1)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["producto", "adicion"],
                name="producto_adicion_unica",
            ),
            models.CheckConstraint(
                condition=Q(maxCantidad__gte=1),
                name="producto_adicion_max_cantidad_positiva",
            ),
        ]

    def __str__(self):
        return f"{self.producto.nombre} - {self.adicion.nombre}"


class ProductoInsumo(models.Model):
    idProductoInsumo = models.AutoField(primary_key=True)
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
    cantidadNecesaria = models.DecimalField(max_digits=12, decimal_places=3)
    esExcluible = models.BooleanField(default=False)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["producto", "insumo"],
                name="producto_insumo_unico",
            ),
            models.CheckConstraint(
                condition=Q(cantidadNecesaria__gt=0),
                name="producto_insumo_cantidad_positiva",
            ),
        ]

    def __str__(self):
        return f"{self.producto.nombre} - {self.insumo.nombre}"


class InventarioProducto(models.Model):
    idInventarioProducto = models.AutoField(primary_key=True)
    sede = models.ForeignKey(
        Sede,
        on_delete=models.PROTECT,
        related_name="inventario_productos",
    )
    producto = models.ForeignKey(
        Producto,
        on_delete=models.PROTECT,
        related_name="inventarios",
    )
    stockActual = models.PositiveIntegerField(default=0)
    stockMinimo = models.PositiveIntegerField(default=0)
    disponible = models.BooleanField(default=True)
    demandaDiaria = models.PositiveIntegerField(default=0)
    fechaActualizacion = models.DateTimeField(auto_now=True)

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
# decimales (igual que ProductoInsumo.cantidadNecesaria).
# El descuento automático de insumos al preparar un pedido se implementa
# en la lógica del flujo de pedidos, no en los modelos.
class InventarioInsumo(models.Model):
    idInventarioInsumo = models.AutoField(primary_key=True)
    sede = models.ForeignKey(
        Sede,
        on_delete=models.PROTECT,
        related_name="inventario_insumos",
    )
    insumo = models.ForeignKey(
        Insumo,
        on_delete=models.PROTECT,
        related_name="inventarios",
    )
    stockActual = models.DecimalField(
        max_digits=12, decimal_places=3, default=0
    )
    stockMinimo = models.DecimalField(
        max_digits=12, decimal_places=3, default=0
    )
    disponible = models.BooleanField(default=True)
    demandaDiaria = models.DecimalField(
        max_digits=12, decimal_places=3, default=0
    )
    fechaActualizacion = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["sede", "insumo"],
                name="inventario_insumo_sede_unico",
            ),
            models.CheckConstraint(
                condition=Q(stockActual__gte=0),
                name="inventario_insumo_stock_actual_no_negativo",
            ),
            models.CheckConstraint(
                condition=Q(stockMinimo__gte=0),
                name="inventario_insumo_stock_minimo_no_negativo",
            ),
            models.CheckConstraint(
                condition=Q(demandaDiaria__gte=0),
                name="inventario_insumo_demanda_no_negativa",
            ),
        ]

    def __str__(self):
        return f"{self.insumo.nombre} - {self.sede.nombre}"


# ---------------------------------------------------------------------------
# Combos
# ---------------------------------------------------------------------------

class Combo(models.Model):
    idCombo = models.AutoField(primary_key=True)
    nombre = models.CharField(max_length=100)
    condicion = models.TextField(blank=True)
    descripcion = models.TextField(blank=True)
    precio = models.DecimalField(max_digits=10, decimal_places=2)
    activo = models.BooleanField(default=True)
    fechaInicio = models.DateField()
    fechaVencimiento = models.DateField()

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=Q(precio__gte=0),
                name="combo_precio_no_negativo",
            ),
            models.CheckConstraint(
                condition=Q(fechaInicio__lte=models.F("fechaVencimiento")),
                name="combo_vigencia_valida",
            ),
        ]

    def __str__(self):
        return self.nombre


class ComboProducto(models.Model):
    idComboProducto = models.AutoField(primary_key=True)
    combo = models.ForeignKey(
        Combo,
        on_delete=models.PROTECT,
        related_name="productos_incluidos",
    )
    producto = models.ForeignKey(
        Producto,
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
    idComboSede = models.AutoField(primary_key=True)
    combo = models.ForeignKey(
        Combo,
        on_delete=models.PROTECT,
        related_name="sedes_disponibles",
    )
    sede = models.ForeignKey(
        Sede,
        on_delete=models.PROTECT,
        related_name="combos_disponibles",
    )
    activo = models.BooleanField(default=True)
    # NULL = sin cupo diario.
    cupoMaxDiario = models.PositiveIntegerField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["combo", "sede"],
                name="combo_sede_unico",
            ),
            models.CheckConstraint(
                condition=Q(cupoMaxDiario__isnull=True) | Q(cupoMaxDiario__gt=0),
                name="combo_sede_cupo_positivo",
            ),
        ]

    def __str__(self):
        return f"{self.combo.nombre} - {self.sede.nombre}"


# ---------------------------------------------------------------------------
# Repartidor, pedidos y facturación
# ---------------------------------------------------------------------------

class Repartidor(models.Model):
    idRepartidor = models.AutoField(primary_key=True)
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


# Pedido NO guarda dinero: subtotal, domicilio, descuento, total y método de
# pago viven en Factura. El carrito se calcula desde DetallePedido.
class Pedido(models.Model):
    idPedido = models.AutoField(primary_key=True)
    numeroPedido = models.CharField(max_length=20, unique=True)
    sede = models.ForeignKey(
        Sede,
        on_delete=models.PROTECT,
        related_name="pedidos",
    )
    # Nullable: pedidos de mostrador sin cliente registrado.
    cliente = models.ForeignKey(
        Cliente,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="pedidos",
    )
    # Operador que creó el pedido (telefónico o mostrador).
    empleado = models.ForeignKey(
        Empleado,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="pedidos_creados",
    )
    # Nullable: pedidos de mostrador no tienen dirección.
    direccionEntrega = models.ForeignKey(
        DireccionEntrega,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="pedidos",
    )
    # Zona usada al validar la cobertura (tarifa, mínimo, reportes por zona).
    zonaCobertura = models.ForeignKey(
        ZonaCobertura,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="pedidos",
    )
    repartidor = models.ForeignKey(
        Repartidor,
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
    fechaCreacion = models.DateTimeField(auto_now_add=True)
    # Minutos.
    tiempoEstimadoEntrega = models.PositiveIntegerField(null=True, blank=True)
    motivoCancelacion = models.TextField(blank=True)
    descripcion = models.CharField(max_length=200, blank=True)

    def __str__(self):
        return f"Pedido {self.numeroPedido}"


class HistorialEstadoPedido(models.Model):
    idHistorialEstadoPedido = models.AutoField(primary_key=True)
    pedido = models.ForeignKey(
        Pedido,
        on_delete=models.PROTECT,
        related_name="historial_estados",
    )
    # Nullable: los cambios automáticos del sistema no tienen usuario.
    usuario = models.ForeignKey(
        Usuario,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="cambios_estado_pedido",
    )
    estado = models.CharField(
        max_length=20,
        choices=EstadoPedido.choices,
    )
    fechaHora = models.DateTimeField(auto_now_add=True)
    observacion = models.TextField(blank=True)

    def __str__(self):
        return f"Pedido {self.pedido_id}: {self.estado}"


class Factura(models.Model):
    idFactura = models.AutoField(primary_key=True)
    pedido = models.OneToOneField(
        Pedido,
        on_delete=models.PROTECT,
        related_name="factura",
    )
    numero = models.CharField(max_length=30, unique=True)
    fechaEmision = models.DateTimeField(auto_now_add=True)
    subtotal = models.DecimalField(max_digits=12, decimal_places=2)
    iva = models.DecimalField(max_digits=12, decimal_places=2)
    costoDomicilio = models.DecimalField(max_digits=12, decimal_places=2)
    valorDescuento = models.DecimalField(
        max_digits=12, decimal_places=2, default=0
    )
    total = models.DecimalField(max_digits=12, decimal_places=2)
    metodoPago = models.CharField(
        max_length=20,
        choices=MetodoPago.choices,
    )
    estadoFactura = models.CharField(
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
                condition=Q(costoDomicilio__gte=0),
                name="factura_costo_domicilio_no_negativo",
            ),
            models.CheckConstraint(
                condition=Q(valorDescuento__gte=0),
                name="factura_valor_descuento_no_negativo",
            ),
        ]

    def __str__(self):
        return self.numero


class DetallePedido(models.Model):
    idDetallePedido = models.AutoField(primary_key=True)
    pedido = models.ForeignKey(
        Pedido,
        on_delete=models.PROTECT,
        related_name="detalles",
    )
    producto = models.ForeignKey(
        Producto,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="detalles_pedido",
    )
    combo = models.ForeignKey(
        Combo,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="detalles_pedido",
    )
    productoTamano = models.ForeignKey(
        ProductoTamano,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="detalles_pedido",
    )
    cantidad = models.PositiveIntegerField()
    # Precio al momento de la compra (no cambia si luego sube el precio).
    precioUnitario = models.DecimalField(max_digits=10, decimal_places=2)
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
                    Q(producto__isnull=False) | Q(productoTamano__isnull=True)
                ),
                name="detalle_tamano_solo_producto",
            ),
            models.CheckConstraint(
                condition=Q(cantidad__gt=0),
                name="detalle_pedido_cantidad_positiva",
            ),
            models.CheckConstraint(
                condition=Q(precioUnitario__gte=0),
                name="detalle_pedido_precio_no_negativo",
            ),
            models.CheckConstraint(
                condition=Q(subtotal__gte=0),
                name="detalle_pedido_subtotal_no_negativo",
            ),
        ]

    def __str__(self):
        return f"Detalle #{self.idDetallePedido} del pedido #{self.pedido_id}"


class DetallePedidoAdicion(models.Model):
    idDetallePedidoAdicion = models.AutoField(primary_key=True)
    detallePedido = models.ForeignKey(
        DetallePedido,
        on_delete=models.PROTECT,
        related_name="adiciones",
    )
    adicion = models.ForeignKey(
        Adicion,
        on_delete=models.PROTECT,
        related_name="detalles_pedido",
    )
    cantidad = models.PositiveIntegerField(default=1)
    precioUnitario = models.DecimalField(max_digits=10, decimal_places=2)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["detallePedido", "adicion"],
                name="detalle_adicion_unica",
            ),
            models.CheckConstraint(
                condition=Q(cantidad__gt=0),
                name="detalle_adicion_cantidad_positiva",
            ),
            models.CheckConstraint(
                condition=Q(precioUnitario__gte=0),
                name="detalle_adicion_precio_no_negativo",
            ),
        ]

    def __str__(self):
        return f"{self.adicion.nombre} - Detalle {self.detallePedido_id}"


# Un registro por pedido: da trazabilidad y permite devolver el cupo si el
# pedido se cancela. El cupo usado en un día se calcula sumando cantidadUsada
# por comboSede y fecha (fechaConsumo).
class ConsumoCupoCombo(models.Model):
    idConsumoCupoCombo = models.AutoField(primary_key=True)
    comboSede = models.ForeignKey(
        ComboSede,
        on_delete=models.PROTECT,
        related_name="consumos_cupo",
    )
    pedido = models.ForeignKey(
        Pedido,
        on_delete=models.PROTECT,
        related_name="consumos_cupo_combo",
    )
    cantidadUsada = models.PositiveIntegerField(default=1)
    fechaConsumo = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=Q(cantidadUsada__gt=0),
                name="consumo_cupo_combo_cantidad_usada_positiva",
            ),
        ]

    def __str__(self):
        return (
            f"Consumo de {self.comboSede.combo.nombre} "
            f"en pedido {self.pedido_id}"
        )
