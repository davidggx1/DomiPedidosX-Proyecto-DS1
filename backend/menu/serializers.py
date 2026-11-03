from decimal import Decimal

from rest_framework import serializers

from .models import Adicion, CategoriaMenu, Insumo, Producto, ProductoAdicion

# Rules for the product image
TAMANO_MAX_BYTES = 2 * 1024 * 1024  # 2 MB
FORMATOS_PERMITIDOS = {"JPEG", "PNG", "WEBP"}


class ProductoImagenSerializer(serializers.ModelSerializer):
    imagen = serializers.ImageField(required=True, allow_empty_file=False)

    class Meta:
        model = Producto
        fields = ["id", "imagen"]
        read_only_fields = ["id"]

    def validate_imagen(self, archivo):
        if archivo.size > TAMANO_MAX_BYTES:
            raise serializers.ValidationError(
                f"La imagen no puede superar {TAMANO_MAX_BYTES // (1024 * 1024)} MB."
            )
        # ImageField already checks with Pillow that it is a real image
        # here we only limit the accepted formats
        if archivo.image.format not in FORMATOS_PERMITIDOS:
            raise serializers.ValidationError(
                "Formato no permitido. Usa JPG, PNG o WebP."
            )
        return archivo


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


class InsumoOpcionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Insumo
        fields = ["id", "nombre", "unidad_medida"]


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
