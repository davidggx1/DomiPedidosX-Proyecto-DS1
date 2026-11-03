import re
import string
import secrets
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from rest_framework_simplejwt.exceptions import AuthenticationFailed
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from django.contrib.auth.password_validation import validate_password
from django.db import transaction
from rest_framework import serializers

from .models import Cliente, TipoDocumento, Usuario, Empleado, Repartidor
from sedes.models import Sede
from .roles import ADMINISTRADOR, obtener_rol, obtener_sede

User = get_user_model()

ROLES_OPERATIVOS = ["OPERADOR", "COCINA", "REPARTIDOR"]
ROLES_PERMITIDOS = ROLES_OPERATIVOS + ["ADMINISTRADOR"]

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

class RegistroEmpleadoSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(
        write_only=True, required=False, allow_blank=True, style={"input_type": "password"}
    )
    nombres = serializers.CharField(max_length=100)
    apellidos = serializers.CharField(max_length=100)
    tipo_documento = serializers.ChoiceField(choices=TipoDocumento.choices)
    num_documento = serializers.CharField(max_length=12)
    celular = serializers.CharField(max_length=10)
    direccion = serializers.CharField(max_length=255)
    rol = serializers.ChoiceField(choices=ROLES_PERMITIDOS)
    sede_id = serializers.IntegerField(required=False, allow_null=True)

    def validate_email(self, value):
        value = value.lower()
        if Usuario.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError("Ya existe una cuenta registrada con este correo.")
        return value

    def validate_celular(self, value):
        if len(value) != 10 or not value.isdigit():
            raise serializers.ValidationError("El teléfono debe contener exactamente 10 dígitos numéricos.")
        return value

    def validate(self, attrs):
        rol = attrs.get("rol")
        sede_id = attrs.get("sede_id")

        # Regla: Exigir sede SIEMPRE que el rol NO sea Administrador
        if rol != "ADMINISTRADOR":
            if not sede_id:
                raise serializers.ValidationError(
                    {"sede_id": f"La sede es obligatoria para el rol {rol}."}
                )
            if not Sede.objects.filter(id=sede_id, activa=True).exists():
                raise serializers.ValidationError(
                    {"sede_id": "La sede seleccionada no existe o se encuentra inactiva."}
                )
        else:
            # Si es Administrador y envió sede_id, validamos que la sede exista si no viene vacía
            if sede_id and not Sede.objects.filter(id=sede_id, activa=True).exists():
                raise serializers.ValidationError(
                    {"sede_id": "La sede seleccionada no existe o se encuentra inactiva."}
                )

        if Empleado.objects.filter(
                tipo_documento=attrs["tipo_documento"],
                num_documento=attrs["num_documento"],
        ).exists():
            raise serializers.ValidationError(
                {"num_documento": "Ya existe un empleado con este número de documento."}
            )

        return attrs

    @transaction.atomic
    def create(self, validated_data):
        email = validated_data.pop("email")
        raw_password = validated_data.pop("password", None)
        rol_nombre = validated_data.pop("rol")
        sede_id = validated_data.pop("sede_id")

        # Generar contraseña temporal si no se provee
        if not raw_password:
            alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
            raw_password = "".join(secrets.choice(alphabet) for _ in range(12))

        # Crear usuario
        usuario = Usuario.objects.create_user(
            username=email,
            email=email,
            password=raw_password,
            is_staff=(rol_nombre == "ADMINISTRADOR"),
        )

        # Asignar a su grupo de Django (Rol)
        grupo, _ = Group.objects.get_or_create(name=rol_nombre)
        usuario.groups.add(grupo)

        sede_obj = Sede.objects.get(id=sede_id) if sede_id else None

        # Crear perfil Empleado
        empleado = Empleado.objects.create(
            usuario=usuario,
            sede=sede_obj,
            tipo_documento=validated_data["tipo_documento"],
            num_documento=validated_data["num_documento"],
            nombres=validated_data["nombres"],
            apellidos=validated_data["apellidos"],
            celular=validated_data["celular"],
            direccion=validated_data["direccion"],
        )

        # Si el rol es Repartidor, crear también su perfil de repartidor disponible
        if rol_nombre == "REPARTIDOR":
            Repartidor.objects.create(empleado=empleado, disponible=True)

        # Guardar la contraseña temporal en el objeto para ser devuelta en la respuesta HTTP
        empleado.contrasena_inicial = raw_password
        return empleado

class EmpleadoListSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(source="usuario.email")
    rol = serializers.SerializerMethodField()
    sede = serializers.CharField(source="sede.nombre", default="N/A")
    sede_id = serializers.IntegerField(source="sede.id", default=None)
    is_active = serializers.BooleanField(source="usuario.is_active")

    class Meta:
        model = Empleado
        fields = [
            "id",
            "nombres",
            "apellidos",
            "email",
            "rol",
            "sede",
            "sede_id",
            "celular",
            "is_active",
        ]

    def get_rol(self, obj):
        grupo = obj.usuario.groups.first()
        return grupo.name if grupo else "SIN_ROL"

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