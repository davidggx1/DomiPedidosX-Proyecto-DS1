from rest_framework import serializers

from .models import CategoriaMenu, Producto

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
