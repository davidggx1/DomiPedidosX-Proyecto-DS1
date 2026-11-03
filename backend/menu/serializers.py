from rest_framework import serializers

from .models import Producto

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
