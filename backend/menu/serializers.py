from decimal import Decimal

from django.db import transaction
from rest_framework import serializers

from inventario.models import InventarioProducto
from sedes.models import Sede

from .models import Adicion, CategoriaMenu, Insumo, Producto, ProductoAdicion, ProductoInsumo

# Rules for the product image (HU-11: only JPG or PNG up to 2 MB)
TAMANO_MAX_BYTES = 2 * 1024 * 1024  # 2 MB
FORMATOS_PERMITIDOS = {"JPEG", "PNG"}


def validar_imagen(archivo):
    """Shared by the image endpoint and the product form"""
    if archivo.size > TAMANO_MAX_BYTES:
        raise serializers.ValidationError(
            f"La imagen no puede superar {TAMANO_MAX_BYTES // (1024 * 1024)} MB."
        )
    # ImageField already checks with Pillow that it is a real image
    # here we only limit the accepted formats
    if archivo.image.format not in FORMATOS_PERMITIDOS:
        raise serializers.ValidationError("Formato no permitido. Usa JPG o PNG.")
    return archivo


class ProductoImagenSerializer(serializers.ModelSerializer):
    imagen = serializers.ImageField(required=True, allow_empty_file=False)

    class Meta:
        model = Producto
        fields = ["id", "imagen"]
        read_only_fields = ["id"]

    def validate_imagen(self, archivo):
        return validar_imagen(archivo)


class ProductoSerializer(serializers.ModelSerializer):
    """
    HU-11: crear, editar y listar productos del menú.

    El catálogo es global; "sedes" indica en qué sedes se ofrece el producto y
    se guarda en InventarioProducto (el mismo registro que lee el menú del cliente).
    Acepta JSON o multipart/form-data (cuando se envía la imagen).
    """

    nombre = serializers.CharField(
        max_length=100,
        error_messages={
            "required": "El nombre es obligatorio.",
            "blank": "El nombre es obligatorio.",
            "null": "El nombre es obligatorio.",
            "max_length": "El nombre no puede superar los 100 caracteres.",
        },
    )
    precio_base = serializers.DecimalField(
        max_digits=10,
        decimal_places=2,
        min_value=Decimal("0.01"),
        error_messages={
            "required": "El precio es obligatorio.",
            "null": "El precio es obligatorio.",
            "invalid": "Escribe un precio válido.",
            "min_value": "El precio debe ser mayor que 0.",
            "max_decimal_places": "Usa máximo 2 decimales.",
        },
    )
    tiempo_preparacion = serializers.IntegerField(
        min_value=1,
        max_value=600,
        error_messages={
            "required": "El tiempo de preparación es obligatorio.",
            "null": "El tiempo de preparación es obligatorio.",
            "invalid": "Escribe los minutos como un número entero.",
            "min_value": "El tiempo de preparación debe ser mayor que 0.",
            "max_value": "El tiempo de preparación no puede superar 600 minutos.",
        },
    )
    categoria = serializers.PrimaryKeyRelatedField(
        queryset=CategoriaMenu.objects.all(),
        error_messages={
            "required": "Selecciona una categoría.",
            "null": "Selecciona una categoría.",
            "does_not_exist": "La categoría seleccionada no existe.",
            "incorrect_type": "Selecciona una categoría.",
        },
    )
    categoria_nombre = serializers.CharField(source="categoria.nombre", read_only=True)
    imagen = serializers.ImageField(
        required=False,
        allow_empty_file=False,
        error_messages={
            "invalid_image": "El archivo no es una imagen válida. Usa JPG o PNG.",
            "invalid": "El archivo no es una imagen válida. Usa JPG o PNG.",
            "empty": "El archivo está vacío.",
        },
    )
    sedes = serializers.PrimaryKeyRelatedField(
        many=True,
        write_only=True,
        allow_empty=False,
        queryset=Sede.objects.filter(activa=True),
        error_messages={
            "required": "Selecciona al menos una sede.",
            "empty": "Selecciona al menos una sede.",
            "not_a_list": "Selecciona al menos una sede.",
        },
    )

    class Meta:
        model = Producto
        fields = [
            "id",
            "nombre",
            "descripcion",
            "imagen",
            "precio_base",
            "tiempo_preparacion",
            "categoria",
            "categoria_nombre",
            "sedes",
            "activo",
        ]
        read_only_fields = ["id"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # The message for a missing/inactive sede lives in the child field
        self.fields["sedes"].child_relation.error_messages["does_not_exist"] = (
            "La sede seleccionada no existe o está inactiva."
        )

    def validate_nombre(self, value):
        nombre = " ".join(value.split())
        if not nombre:
            raise serializers.ValidationError("El nombre es obligatorio.")
        return nombre

    def validate_categoria(self, categoria):
        # An existing product can stay in its category even if it was deactivated later
        misma = self.instance is not None and self.instance.categoria_id == categoria.id
        if not categoria.activa and not misma:
            raise serializers.ValidationError("La categoría seleccionada está inactiva.")
        return categoria

    def validate_imagen(self, archivo):
        return validar_imagen(archivo)

    def to_representation(self, producto):
        datos = super().to_representation(producto)
        # Uses the prefetched inventories when the view provides them
        datos["sedes"] = sorted(
            inventario.sede_id
            for inventario in producto.inventarios.all()
            if inventario.disponible
        )
        return datos

    @transaction.atomic
    def create(self, validated_data):
        sedes = validated_data.pop("sedes")
        producto = super().create(validated_data)
        self._guardar_sedes(producto, sedes)
        return producto

    @transaction.atomic
    def update(self, instance, validated_data):
        sedes = validated_data.pop("sedes", None)
        imagen_anterior = instance.imagen.name if "imagen" in validated_data else ""
        producto = super().update(instance, validated_data)
        if sedes is not None:
            self._guardar_sedes(producto, sedes)
        # When replacing the image, the old file is deleted from storage
        if imagen_anterior and imagen_anterior != producto.imagen.name:
            producto.imagen.storage.delete(imagen_anterior)
        return producto

    @staticmethod
    def _guardar_sedes(producto, sedes):
        """Selected sedes offer the product; the rest stop offering it (rows are kept)"""
        ids = [sede.id for sede in sedes]
        for sede in sedes:
            InventarioProducto.objects.update_or_create(
                sede=sede, producto=producto, defaults={"disponible": True}
            )
        InventarioProducto.objects.filter(producto=producto).exclude(
            sede_id__in=ids
        ).update(disponible=False)


class CategoriaMenuSerializer(serializers.ModelSerializer):
    nombre = serializers.CharField(
        max_length=50,
        error_messages={
            "required": "El nombre de la categoría es obligatorio.",
            "blank": "El nombre de la categoría es obligatorio.",
            "null": "El nombre de la categoría es obligatorio.",
            "max_length": "El nombre no puede superar los 50 caracteres.",
        },
    )
    total_productos = serializers.SerializerMethodField()

    class Meta:
        model = CategoriaMenu
        fields = ["id", "nombre", "descripcion", "activa", "total_productos"]
        read_only_fields = ["id"]

    def get_total_productos(self, categoria):
        # the list view already annotates it, otherwise we count here
        total = getattr(categoria, "total_productos", None)
        return total if total is not None else categoria.productos.count()

    def validate_nombre(self, value):
        # trim and collapse inner spaces so "Pizzas  " and "Pizzas" are the same
        nombre = " ".join(value.split())
        if not nombre:
            raise serializers.ValidationError("El nombre de la categoría es obligatorio.")

        repetidas = CategoriaMenu.objects.filter(nombre__iexact=nombre)
        if self.instance:
            # renaming to its own name (or changing the case) is fine
            repetidas = repetidas.exclude(pk=self.instance.pk)
        if repetidas.exists():
            raise serializers.ValidationError("Ya existe una categoría con este nombre.")
        return nombre


class InsumoSerializer(serializers.ModelSerializer):
    """HU-77: catálogo de ingredientes (insumos) del restaurante."""

    class Meta:
        model = Insumo
        fields = ["id", "nombre", "unidad_medida", "activo"]
        extra_kwargs = {
            "nombre": {
                # La unicidad se valida abajo, con un mensaje en español.
                "validators": [],
                "error_messages": {
                    "required": "El nombre del ingrediente es obligatorio.",
                    "blank": "El nombre del ingrediente es obligatorio.",
                    "max_length": "El nombre no puede superar los 100 caracteres.",
                },
            },
            "unidad_medida": {
                "error_messages": {
                    "required": "Selecciona la unidad de medida.",
                    "invalid_choice": "Unidad de medida no válida.",
                }
            },
        }

    def validate_nombre(self, value):
        nombre = " ".join(value.split())
        if not nombre:
            raise serializers.ValidationError("El nombre del ingrediente es obligatorio.")

        repetido = Insumo.objects.filter(nombre__iexact=nombre)
        if self.instance is not None:
            repetido = repetido.exclude(pk=self.instance.pk)
        repetido = repetido.first()
        if repetido is not None:
            if repetido.activo:
                raise serializers.ValidationError("Ya existe un ingrediente con este nombre.")
            raise serializers.ValidationError(
                "Ya existe un ingrediente eliminado con este nombre. Restáuralo en lugar de crear uno nuevo."
            )
        return nombre


class ProductoOpcionSerializer(serializers.ModelSerializer):
    categoria_nombre = serializers.CharField(source="categoria.nombre", read_only=True)

    class Meta:
        model = Producto
        fields = ["id", "nombre", "categoria_nombre"]


class AdicionSerializer(serializers.ModelSerializer):
    """HU-76: catálogo de adiciones (queso extra, tocineta extra...)."""

    insumo_nombre = serializers.CharField(source="insumo.nombre", read_only=True)
    precio = serializers.DecimalField(
        max_digits=10,
        decimal_places=2,
        min_value=Decimal("0"),
        error_messages={
            "required": "El precio es obligatorio.",
            "invalid": "Escribe un precio válido.",
            "min_value": "El precio no puede ser negativo.",
        },
    )

    class Meta:
        model = Adicion
        fields = [
            "id",
            "nombre",
            "descripcion",
            "imagen_url",
            "precio",
            "insumo",
            "insumo_nombre",
            "activa",
        ]
        extra_kwargs = {
            "nombre": {
                "error_messages": {
                    "required": "El nombre es obligatorio.",
                    "blank": "El nombre es obligatorio.",
                }
            },
            "insumo": {
                "error_messages": {
                    "required": "Selecciona el insumo que consume la adición.",
                    "null": "Selecciona el insumo que consume la adición.",
                    "does_not_exist": "El insumo seleccionado no existe.",
                }
            },
        }

    def validate_insumo(self, insumo):
        if not insumo.activo:
            raise serializers.ValidationError("El insumo seleccionado está inactivo.")
        return insumo

    def validate(self, attrs):
        # No puede haber dos adiciones ACTIVAS con el mismo nombre.
        nombre = attrs.get("nombre", getattr(self.instance, "nombre", ""))
        activa = attrs.get("activa", getattr(self.instance, "activa", True))
        if activa:
            repetidas = Adicion.objects.filter(nombre__iexact=nombre, activa=True)
            if self.instance is not None:
                repetidas = repetidas.exclude(pk=self.instance.pk)
            if repetidas.exists():
                raise serializers.ValidationError(
                    {"nombre": "Ya existe una adición activa con este nombre."}
                )
        return attrs


class ProductoAdicionSerializer(serializers.ModelSerializer):
    """Adiciones que se ofrecen en un producto concreto."""

    adicion_nombre = serializers.CharField(source="adicion.nombre", read_only=True)
    adicion_precio = serializers.DecimalField(
        source="adicion.precio", max_digits=10, decimal_places=2, read_only=True
    )
    adicion_activa = serializers.BooleanField(source="adicion.activa", read_only=True)
    max_cantidad = serializers.IntegerField(
        min_value=1,
        required=False,
        error_messages={
            "invalid": "Escribe un número entero.",
            "min_value": "La cantidad máxima debe ser al menos 1.",
        },
    )

    class Meta:
        model = ProductoAdicion
        fields = [
            "id",
            "adicion",
            "adicion_nombre",
            "adicion_precio",
            "adicion_activa",
            "max_cantidad",
        ]
        extra_kwargs = {
            "adicion": {
                "error_messages": {
                    "required": "Selecciona una adición.",
                    "null": "Selecciona una adición.",
                    "does_not_exist": "La adición seleccionada no existe.",
                }
            },
        }

    def validate_adicion(self, adicion):
        if not adicion.activa:
            raise serializers.ValidationError("No se puede asignar una adición eliminada.")
        return adicion

    def validate(self, attrs):
        producto = self.context["producto"]
        adicion = attrs.get("adicion", getattr(self.instance, "adicion", None))
        repetidas = ProductoAdicion.objects.filter(producto=producto, adicion=adicion)
        if self.instance is not None:
            repetidas = repetidas.exclude(pk=self.instance.pk)
        if repetidas.exists():
            raise serializers.ValidationError(
                {"adicion": "Esta adición ya está asignada al producto."}
            )
        return attrs


class ProductoInsumoSerializer(serializers.ModelSerializer):
    """HU-77: ingredientes de un producto y si el cliente puede quitarlos."""

    insumo_nombre = serializers.CharField(source="insumo.nombre", read_only=True)
    unidad_medida = serializers.CharField(source="insumo.unidad_medida", read_only=True)
    insumo_activo = serializers.BooleanField(source="insumo.activo", read_only=True)
    cantidad_necesaria = serializers.DecimalField(
        max_digits=12,
        decimal_places=3,
        min_value=Decimal("0.001"),
        error_messages={
            "required": "La cantidad es obligatoria.",
            "invalid": "Escribe una cantidad válida.",
            "min_value": "La cantidad debe ser mayor que 0.",
            "max_decimal_places": "Usa máximo 3 decimales.",
        },
    )

    class Meta:
        model = ProductoInsumo
        fields = [
            "id",
            "insumo",
            "insumo_nombre",
            "unidad_medida",
            "insumo_activo",
            "cantidad_necesaria",
            "es_excluible",
        ]
        extra_kwargs = {
            "insumo": {
                "error_messages": {
                    "required": "Selecciona un ingrediente.",
                    "null": "Selecciona un ingrediente.",
                    "does_not_exist": "El ingrediente seleccionado no existe.",
                }
            },
        }

    def validate_insumo(self, insumo):
        if not insumo.activo:
            raise serializers.ValidationError("No se puede usar un ingrediente eliminado.")
        return insumo

    def validate(self, attrs):
        producto = self.context["producto"]
        insumo = attrs.get("insumo", getattr(self.instance, "insumo", None))
        repetidos = ProductoInsumo.objects.filter(producto=producto, insumo=insumo)
        if self.instance is not None:
            repetidos = repetidos.exclude(pk=self.instance.pk)
        if repetidos.exists():
            raise serializers.ValidationError(
                {"insumo": "Este ingrediente ya está en el producto."}
            )
        return attrs
