import re
from django.contrib.auth import get_user_model
from rest_framework_simplejwt.exceptions import AuthenticationFailed
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from django.contrib.auth.password_validation import validate_password
from django.db import transaction
from rest_framework import serializers

from .models import Cliente, TipoDocumento, Usuario
from .roles import ADMINISTRADOR, obtener_rol, obtener_sede


class RegistroClienteSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, style={"input_type": "password"})
    tipo_documento = serializers.ChoiceField(choices=TipoDocumento.choices)
    num_documento = serializers.CharField(max_length=12)
    nombres = serializers.CharField(max_length=100)
    apellidos = serializers.CharField(max_length=100)
    celular = serializers.CharField(max_length=10)
    fecha_nacimiento = serializers.DateField()

    def validate_email(self, value):
        value = value.lower()
        if Usuario.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError("Ya existe una cuenta con este correo.")
        return value

    def validate_celular(self, value):
        if not value:
            raise serializers.ValidationError("El teléfono celular es obligatorio.")

        # Validación de 10 dígitos numéricos
        if not re.match(r"^\d{10}$", value):
            raise serializers.ValidationError(
                "El número de teléfono debe contener exactamente 10 dígitos numéricos."
            )

        # Validación de unicidad
        if Cliente.objects.filter(celular=value).exists():
            raise serializers.ValidationError(
                "Este número de teléfono ya está registrado en otra cuenta."
            )
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


class LoginSerializer(TokenObtainPairSerializer):
    # Mensaje genérico: no revela si falló el correo o la contraseña.
    default_error_messages = {"no_active_account": "Credenciales inválidas."}

    def validate(self, attrs):
        Usuario = get_user_model()
        email = attrs.get(self.username_field, "")
        password = attrs.get("password", "")
        usuario = Usuario.objects.filter(email__iexact=email).first()
        # Solo se avisa "inactiva" si la contraseña es correcta, para no
        # revelar a un extraño qué correos existen.
        if usuario and not usuario.is_active and usuario.check_password(password):
            raise AuthenticationFailed("La cuenta está inactiva.", "cuenta_inactiva")
        return super().validate(attrs)

class LoginPersonalSerializer(LoginSerializer):
    def validate(self, attrs):
        data = super().validate(attrs)  # credenciales, cuenta activa, tokens
        rol = obtener_rol(self.user)
        sede = obtener_sede(self.user)
        # Un cliente, o un empleado sin sede, no entra por aquí (mensaje genérico).
        if rol is None or (rol != ADMINISTRADOR and sede is None):
            raise AuthenticationFailed("Credenciales inválidas.", "no_active_account")
        data["rol"] = rol
        data["sede_id"] = sede.pk if sede else None
        return data        