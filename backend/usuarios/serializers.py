from django.contrib.auth.password_validation import validate_password
from django.db import transaction
from rest_framework import serializers

from .models import Cliente, TipoDocumento, Usuario


class RegistroClienteSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, style={"input_type": "password"})
    tipo_documento = serializers.ChoiceField(choices=TipoDocumento.choices)
    num_documento = serializers.CharField(max_length=12)
    nombres = serializers.CharField(max_length=100)
    apellidos = serializers.CharField(max_length=100)
    celular = serializers.CharField(max_length=15)
    fecha_nacimiento = serializers.DateField()

    def validate_email(self, value):
        value = value.lower()
        if Usuario.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError("Ya existe una cuenta con este correo.")
        return value

    def validate_password(self, value):
        # Aplica las reglas de settings (mínimo 8 caracteres, no común, etc.)
        validate_password(value)
        return value

    def validate(self, attrs):
        if Cliente.objects.filter(
            tipo_documento=attrs["tipo_documento"],
            num_documento=attrs["num_documento"],
        ).exists():
            raise serializers.ValidationError(
                {"num_documento": "Ya existe un cliente con este documento."}
            )
        return attrs

    @transaction.atomic
    def create(self, validated_data):
        email = validated_data.pop("email")
        password = validated_data.pop("password")
        # create_user cifra la contraseña (hash). El username se rellena con el correo.
        usuario = Usuario.objects.create_user(
            username=email, email=email, password=password
        )
        return Cliente.objects.create(usuario=usuario, **validated_data)