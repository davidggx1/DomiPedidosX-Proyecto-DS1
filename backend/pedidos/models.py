from django.contrib.auth.models import AbstractUser
from django.db import models

#para la regla XOR de pedidos o combos, pero no ambos:
from django.db.models import Q

# Create your models here.
#Pendiente: se debe revisar que los tipos de datos en efecto, coincidan con el ER de forma adecuada.
#debemos confirmar los atributos y relaciones con tu diagrama ER antes de las migraciones.

#Clase para reutilizar los tipos de doumentos de los usuarios
class TipoDocumento(models.TextChoices):
    CC = "CC", "Cédula de ciudadanía (C.C.)"
    TI = "TI", "Tarjeta de identidad (T.I.)"
    CE = "CE", "Cédula de extranjería (C.E.)"
    PA = "PA", "Pasaporte"
    RC = "RC", "Registro civil"
    PPT = "PPT", "Permiso por Protección Temporal (PPT)"

#La reutilizamos en factura y en pedido
class MetodoPago(models.TextChoices):
    EFECTIVO = "efectivo", "Efectivo"
    TARJETA = "tarjeta", "Tarjeta"
    TRANSFERENCIA = "transferencia", "Transferencia"


#AbstractUser ya proporciona contraseña con hash, estado de activación,
# permisos, grupos y campos de autenticación.
#Los roles del usuario se manejaran con grupos y permisos de django
#el rol definira que pantalla ve cada user (cliente, repartidor, etc)
# y que operaciones permitidas tiene
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

#se agrega restriccion  para evitar coordenadas geograficas fuera de rango
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
    radio = models.FloatField()
    centroLatitud = models.FloatField()
    centroLongitud = models.FloatField()

    tarifaDomicilio = models.DecimalField(
        max_digits=10, 
        decimal_places=2)
    tiempoEstimado = models.IntegerField()
    pedidoMinimo = models.DecimalField(max_digits=10, decimal_places=2)
    activo = models.BooleanField(default=True)

    #restricciones adicionales
    #Hay que fijar la unidad de radio para hacer los calculos de la cobertura. 
    #Se recomienda en Kms
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
        choices=TipoDocumento.choices, #aqui esta la conexion con la primera clase, tipoDocumento controlado
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
            #un cliente puede tener varias direcciones, pero maximo 1 principal
            models.UniqueConstraint(
                fields=["cliente"],
                condition=Q(esPrincipal=True),
                name="una_direccion_principal_por_cliente",
            ),
            #validaciones geograficas: latitud y longitud
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

    pedido = models.ForeignKey(
    "Pedido",
    on_delete=models.SET_NULL,
    related_name="notificaciones",
    null=True,
    blank=True,
    )

    mensaje = models.TextField()
    tipo = models.CharField(max_length=30)
    fechaCreacion = models.DateTimeField(auto_now_add=True)
    leida = models.BooleanField(default=False)

    def __str__(self):
        return f"Notificación {self.idNotificacion}"


class CapacidadSede(models.Model):
    idCapacidadSede = models.AutoField(primary_key=True)
    sede = models.ForeignKey(
        Sede,
        on_delete=models.PROTECT,
        related_name="capacidades",
    )
    
    horarioInicio = models.TimeField()
    horaFin = models.TimeField()

    capacidadMaxima = models.PositiveIntegerField()
    maxPedidosSimultaneos = models.PositiveIntegerField()
    #verificar umbralAlerta. Preguntarle a samuel porque no se muy bien que es.
    umbralAlerta = models.PositiveIntegerField()

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=Q(horarioInicio__lt=models.F("horaFin")),
                name="capacidad_intervalo_horario_valido",
            ),
            models.CheckConstraint(
                condition=Q(capacidadMaxima__gt=0),
                name="capacidad_maxima_positiva",
            ),
            models.CheckConstraint(
                condition=Q(maxPedidosSimultaneos__gt=0),
                name="capacidad_pedidos_simultaneos_positiva",
            ),
            models.CheckConstraint(
                condition=(
                    Q(umbralAlerta__lte=models.F("maxPedidosSimultaneos"))
                ),
                name="capacidad_umbral_dentro_del_limite",
            ),
            models.UniqueConstraint(
                fields=["sede", "horarioInicio", "horaFin"],
                name="capacidad_intervalo_unico_por_sede",
            ),
        ]


    def __str__(self):
        return f"Capacidad de {self.sede.nombre}"


class HorarioSede(models.Model):
    class DiaSemana(models.TextChoices):
        LUNES = "lunes", "Lunes"
        MARTES = "martes", "Martes"
        MIERCOLES = "miercoles", "Miércoles"
        JUEVES = "jueves", "Jueves"
        VIERNES = "viernes", "Viernes"
        SABADO = "sabado", "Sábado"
        DOMINGO = "domingo", "Domingo"

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
                fields=[
                    "sede",
                    "diaSemana",
                    "horaApertura",
                    "horaCierre",
                ],
                name="horario_sede_intervalo_unico",
            ),
        ]

    def __str__(self):
        return (
            f"{self.sede.nombre} - "
            f"{self.get_diaSemana_display()}: "
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


    #un dia marcado como cerrado no necesita horas
    #por el contrario, si abre ese dia, deben estar y el cierre es posterior a la apertura
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


class HistorialEstadoPedido(models.Model):
    idHistorialEstadoPedido = models.AutoField(primary_key=True)
    pedido = models.ForeignKey(
        "Pedido",
        on_delete=models.PROTECT,
        related_name="historial_estados",
    )

    usuario = models.ForeignKey(
        Usuario,
        on_delete=models.PROTECT,
        related_name="cambios_estado_pedido",
    )

    estado = models.CharField(max_length=30)
    fechaHora = models.DateTimeField(auto_now_add=True)
    #observacion no esta en el ER pero aporta trazabilidad, es buena idea agregarlo al ER
    observacion = models.TextField(blank=True)

    def __str__(self):
        return f"Pedido {self.pedido_id}: {self.estado}"

class CategoriaMenu(models.Model):
    idCategoriaMenu = models.AutoField(primary_key=True)
    nombre = models.CharField(max_length=50)
    descripcion = models.TextField(blank=True)
    activa = models.BooleanField(default=True)

#asumismos un catalogo global unico, si no es asi, hay que revisar esta restriccion
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
        related_name="productos"
    )
    nombre = models.CharField(max_length=100)
    descripcion = models.TextField(blank=True)
    imagenUrl = models.URLField(
        max_length=500,
        blank=True,
    )
    precioBase = models.DecimalField(max_digits=10, decimal_places=2)
    tiempoPreparacion = models.PositiveIntegerField()
    activo = models.BooleanField(default=True)



    tipoControlStock = models.CharField(
        max_length=10,
        choices=TipoControlStock.choices,
        default=TipoControlStock.NINGUNO,
    )

#El precio base puede ser cero si existen productos promocionales gratuitos.
    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=Q(precioBase__gte=0),
                name="producto_precio_base_no_negativo",
            ),
        ]


    def __str__(self):
        return self.nombre


class ProductoTamano(models.Model):
    idProductoTamano = models.AutoField(primary_key=True)
    producto = models.ForeignKey(
        Producto,
        on_delete=models.PROTECT,
        related_name="tamanos"
    )
    nombre = models.CharField(max_length=30)
    precioAdicional = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0
    )
    activo = models.BooleanField(default=True)

#deberiamos agregar un check que no permita que el precio sea negativo (suppongo). 
#esta decision queda pendiente porque no se la entendi a gpt
#puede ser negativo si el negocio quiere ofrecer un tamaño más económico que el precio base.
    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["producto", "nombre"],
                name="producto_tamano_nombre_unico",
            ),
        ]

    def __str__(self):
        return f"{self.producto.nombre} - {self.nombre}"


class Adicion(models.Model):
    idAdicion = models.AutoField(primary_key=True)
    idInsumo = models.ForeignKey(
        Insumo,
        on_delete=models.PROTECT,
        related_name="insumos"
        )
    nombre = models.CharField(max_length=80)
    descripcion = models.TextField(blank=True)
    imagenUrl = models.URLField(
        max_length=500,
        blank=True,
    )
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
        related_name="adiciones_disponibles"
    )
    adicion = models.ForeignKey(
        Adicion,
        on_delete=models.PROTECT,
        related_name="productos"
    )
    maxCantidad = models.PositiveIntegerField(default=1)

#No se registra dos veces la misma adicion para un mismo producto
    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["producto", "adicion"],
                name="producto_adicion_unica",
            ),
            models.CheckConstraint(
                condition=models.Q(maxCantidad__gte=1),
                name="producto_adicion_max_cantidad_positiva",
            ),
        ]

    def __str__(self):
        return f"{self.producto.nombre} - {self.adicion.nombre}"

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
        ]

    def __str__(self):
        return self.nombre


class ComboProducto(models.Model):
    idComboProducto = models.AutoField(primary_key=True)
    combo = models.ForeignKey(
        Combo,
        on_delete=models.PROTECT,
        related_name="productos_incluidos"
    )
    producto = models.ForeignKey(
        Producto,
        on_delete=models.PROTECT,
        related_name="combos"
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
        related_name="sedes_disponibles"
    )
    sede = models.ForeignKey(
        Sede,
        on_delete=models.PROTECT,
        related_name="combos_disponibles"
    )
    activo = models.BooleanField(default=True)
    cupoMaxDiario = models.PositiveIntegerField(
        null=True,
        blank=True,
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["combo", "sede"],
                name="combo_sede_unico",
            ),
            models.CheckConstraint(
                condition=(
                    Q(cupoMaxDiario__isnull=True)
                    | Q(cupoMaxDiario__gt=0)
                ),
                name="combo_sede_cupo_positivo",
            ),
        ]

    def __str__(self):
        return f"{self.combo.nombre} - {self.sede.nombre}"

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
            models.CheckConstraint(
                condition=models.Q(stockActual__gte=0),
                name="inventario_producto_stock_actual_no_negativo",
            ),
            models.CheckConstraint(
                condition=models.Q(stockMinimo__gte=0),
                name="inventario_producto_stock_minimo_no_negativo",
            ),
            models.CheckConstraint(
                condition=models.Q(demandaDiaria__gte=0),
                name="inventario_producto_demanda_no_negativa",
            ),
        ]

    def __str__(self):
        return f"{self.producto.nombre} - {self.sede.nombre}"


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
        choices=UnidadMedida.choices)
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



#Nota: Si el sistema descuenta ingredientes automáticamente al preparar un pedido,
#  habrá que implementar esa lógica en el flujo de pedidos, no solamente en estos modelos.
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

    stockActual = models.PositiveIntegerField(default=0)
    stockMinimo = models.PositiveIntegerField(default=0)
    disponible = models.BooleanField(default=True)
    demandaDiaria = models.PositiveIntegerField(default=0)
    fechaActualizacion = models.DateTimeField(auto_now=True)


    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["sede", "insumo"],
                name="inventario_insumo_sede_unico",
            ),
            models.CheckConstraint(
                condition=models.Q(stockActual__gte=0),
                name="inventario_insumo_stock_actual_no_negativo",
            ),
            models.CheckConstraint(
                condition=models.Q(stockMinimo__gte=0),
                name="inventario_insumo_stock_minimo_no_negativo",
            ),
            models.CheckConstraint(
                condition=models.Q(demandaDiaria__gte=0),
                name="inventario_insumo_demanda_no_negativa",
            ),
        ]



    def __str__(self):
        return f"{self.insumo.nombre} - {self.sede.nombre}"


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
    cantidadNecesaria = models.DecimalField(
        max_digits=12,
        decimal_places=3,
    )

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


class Repartidor(models.Model):
    idRepartidor = models.AutoField(primary_key=True)
    empleado = models.OneToOneField(
        Empleado,
        on_delete=models.PROTECT,
        related_name="perfil_repartidor",
    )
    disponible = models.BooleanField(default=True)
    latitud = models.FloatField()
    longitud = models.FloatField()

    def __str__(self):
        return f"Repartidor: {self.empleado.nombres} {self.empleado.apellidos}"


class Factura(models.Model):
    idFactura = models.AutoField(primary_key=True)
    pedido = models.OneToOneField(
        "Pedido",
        on_delete=models.PROTECT,
        related_name="factura",
    )
    numero = models.CharField(max_length=30, unique=True)
    fechaEmision = models.DateTimeField(auto_now_add=True)
    subtotal = models.DecimalField(max_digits=12, decimal_places=2)
    iva = models.DecimalField(max_digits=12, decimal_places=2)
    costoDomicilio = models.DecimalField(max_digits=12, decimal_places=2)
    valorDescuento = models.DecimalField(max_digits=12, decimal_places=2)    
    total = models.DecimalField(max_digits=12, decimal_places=2)


    metodoPago = models.CharField(
        max_length=20,
        choices=MetodoPago.choices,
    )

    estadoFactura = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=Q(subtotal__gte=0),
                name="factura_subtotal_no_negativo",
            ),
            models.CheckConstraint(
                condition=Q(iva__gte=0),
                name="factura_iva_no_negativos",
            ),
            models.CheckConstraint(
                condition=Q(total__gte=0),
                name="factura_total_no_negativo",
            ),
            models.CheckConstraint(
                condition=Q(costoDomicilio__gte=0),
                name="factura_costo_domicilio_no_negativos",
            ),
            models.CheckConstraint(
                condition=Q(valorDescuento__gte=0),
                name="factura_valor_descuento_no_negativo",
            ),
        ]

    def __str__(self):
        return self.numero

    
class Pedido(models.Model):
    class Estado(models.TextChoices):
        PENDIENTE = "pendiente", "Pendiente"
        CONFIRMADO = "confirmado", "Confirmado"
        EN_PREPARACION = "en_preparacion", "En preparación"
        LISTO = "listo", "Listo"
        EN_CAMINO = "en_camino", "En camino"
        ENTREGADO = "entregado", "Entregado"
        CANCELADO = "cancelado", "Cancelado"

    idPedido = models.AutoField(primary_key=True)
    numeroPedido = models.CharField(
    max_length=20,
    unique=True,
    )
    cliente = models.ForeignKey(
        Cliente,
        on_delete=models.PROTECT,
        related_name="pedidos",
    )
    sede = models.ForeignKey(
        Sede,
        on_delete=models.PROTECT,
        related_name="pedidos",
    )
    direccionEntrega = models.ForeignKey(
        DireccionEntrega,
        on_delete=models.PROTECT,
        related_name="pedidos",
    )
    repartidor = models.ForeignKey(
        Repartidor,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="pedidos_asignados",
    )

    estado = models.CharField(
        max_length=20,
        choices=Estado.choices,
        default=Estado.PENDIENTE,
    )
    metodoPago = models.CharField(
        max_length=20,
        choices=MetodoPago.choices,
    )
    fechaCreacion = models.DateTimeField(auto_now_add=True)
    subtotal = models.DecimalField(max_digits=12, decimal_places=2)
    tarifaDomicilio = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=0,
        )
    total = models.DecimalField(max_digits=12, decimal_places=2)

    tiempoEstimadoEntrega = models.PositiveIntegerField(
        null=True,
        blank=True,
    )

    motivoCancelacion = models.TextField(blank=True)
    descripcion = models.CharField(max_length=200)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=Q(subtotal__gte=0),
                name="pedido_subtotal_no_negativo",
            ),
            models.CheckConstraint(
                condition=Q(tarifaDomicilio__gte=0),
                name="pedido_tarifa_no_negativa",
            ),
            models.CheckConstraint(
                condition=Q(total__gte=0),
                name="pedido_total_no_negativo",
            ),
        ]


    def __str__(self):
        return f"Pedido {self.idPedido}"
    

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
    precioUnitario = models.DecimalField(
        max_digits=10,
        decimal_places=2,
    )
    subtotal = models.DecimalField(
        max_digits=12,
        decimal_places=2,
    )

    observaciones = models.CharField(max_length=300)


    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=(
                    (
                        Q(producto__isnull=False)
                        & Q(combo__isnull=True)
                    )
                    |
                    (
                        Q(producto__isnull=True)
                        & Q(combo__isnull=False)
                    )
                ),
                name="detalle_pedido_producto_o_combo",
            ),
            models.CheckConstraint(
                condition=(
                    Q(producto__isnull=False)
                    | Q(productoTamano__isnull=True)
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

#con esto garantizamos el XOR, al haber importado al inicio del archivo el modulo Q
    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=(
                    (Q(producto__isnull=False) & Q(combo__isnull=True))
                    |
                    (Q(producto__isnull=True) & Q(combo__isnull=False))
                ),
                name="detalle_pedido_producto_o_combo"
            )
        ]

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
    precioUnitario = models.DecimalField(
        max_digits=10,
        decimal_places=2,
    )

    precioUnitario = models.DecimalField(
        max_digits=12,
        decimal_places=2,
    )


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
        return (
            f"{self.adicion.nombre} - "
            f"Detalle {self.detallePedido_id}"
        )


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
                condition=Q(cantidad__gt=0),
                name="consumo_cupo_cantidad_positiva",
            ),
        ]


    def __str__(self):
        return (
            f"Consumo de {self.comboSede.combo.nombre} "
            f"en pedido {self.pedido_id}"
        )