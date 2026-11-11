"""
HU-05 · Restablecer la contraseña olvidada.

Vive en un módulo aparte de views.py, como cuentas.py.

1. POST /api/usuarios/contrasena/solicitar/ {email}
   Si existe una cuenta activa con ese correo, le envía un enlace al frontend
   con `uid` y `token`. La respuesta es la misma exista o no (criterio 1), para
   no revelar qué correos están registrados.
2. POST /api/usuarios/contrasena/restablecer/ {uid, token, password}
   Valida el token y guarda la nueva contraseña con hash (criterio 2).

El token es el de Django (`default_token_generator`): vence a la hora
(PASSWORD_RESET_TIMEOUT) y deja de servir al primer uso, porque se calcula con
el hash de la contraseña, que cambia al restablecerla (criterio 3).
"""
import logging

from django.conf import settings
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.tokens import default_token_generator
from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.mail import send_mail
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from drf_spectacular.utils import extend_schema
from rest_framework import serializers, status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Usuario

logger = logging.getLogger(__name__)

MENSAJE_SOLICITUD = (
    "Si el correo está registrado, te enviamos un enlace para restablecer tu contraseña. "
    "Revisa tu bandeja de entrada; el enlace vence en 1 hora."
)
ENLACE_INVALIDO = "El enlace no es válido o ya expiró. Solicita uno nuevo."


def enlace_restablecer(usuario):
    uid = urlsafe_base64_encode(force_bytes(usuario.pk))
    token = default_token_generator.make_token(usuario)
    return f"{settings.FRONTEND_URL}/restablecer-contrasena?uid={uid}&token={token}"


def enviar_correo_restablecer(usuario):
    """Un fallo del correo no cambia la respuesta: así tampoco se revela si la cuenta existe."""
    perfil = getattr(usuario, "cliente", None) or getattr(usuario, "empleado", None)
    saludo = f"Hola {perfil.nombres}," if perfil else "Hola,"
    mensaje = "\n".join([
        saludo,
        "",
        "Recibimos una solicitud para restablecer la contraseña de tu cuenta en DomiPedidosX.",
        "Para elegir una nueva, abre este enlace (vence en 1 hora y solo sirve una vez):",
        "",
        enlace_restablecer(usuario),
        "",
        "Si no fuiste tú, ignora este correo: tu contraseña actual sigue funcionando.",
        "",
        "DomiPedidosX",
    ])
    try:
        send_mail(
            subject="Restablece tu contraseña",
            message=mensaje,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[usuario.email],
        )
    except Exception:
        logger.exception("No se pudo enviar el correo para restablecer la contraseña de %s", usuario.pk)


class SolicitarRestablecimientoSerializer(serializers.Serializer):
    email = serializers.EmailField()


class RestablecerContrasenaSerializer(serializers.Serializer):
    uid = serializers.CharField()
    token = serializers.CharField()
    password = serializers.CharField(write_only=True, style={"input_type": "password"})

    def validate(self, attrs):
        try:
            pk = force_str(urlsafe_base64_decode(attrs["uid"]))
            usuario = Usuario.objects.get(pk=pk, is_active=True)
        except (ValueError, TypeError, OverflowError, Usuario.DoesNotExist):
            usuario = None
        if usuario is None or not default_token_generator.check_token(usuario, attrs["token"]):
            raise serializers.ValidationError({"detail": ENLACE_INVALIDO})

        # Mínimo 8 caracteres, no común, no parecida al correo (AUTH_PASSWORD_VALIDATORS).
        try:
            validate_password(attrs["password"], usuario)
        except DjangoValidationError as error:
            raise serializers.ValidationError({"password": list(error.messages)})
        attrs["usuario"] = usuario
        return attrs

    def save(self):
        usuario = self.validated_data["usuario"]
        usuario.set_password(self.validated_data["password"])
        usuario.save(update_fields=["password"])
        return usuario


class SolicitarRestablecimientoView(APIView):
    """POST /api/usuarios/contrasena/solicitar/ · Envía el enlace para restablecer la contraseña."""

    # Públicas: quien olvidó la contraseña no tiene sesión.
    permission_classes = [AllowAny]
    authentication_classes = []

    @extend_schema(request=SolicitarRestablecimientoSerializer, responses={200: None})
    def post(self, request):
        datos = SolicitarRestablecimientoSerializer(data=request.data)
        datos.is_valid(raise_exception=True)
        usuario = Usuario.objects.filter(email__iexact=datos.validated_data["email"], is_active=True).first()
        if usuario is not None:
            enviar_correo_restablecer(usuario)
        return Response({"detail": MENSAJE_SOLICITUD})


class RestablecerContrasenaView(APIView):
    """POST /api/usuarios/contrasena/restablecer/ · Guarda la nueva contraseña si el enlace es válido."""

    permission_classes = [AllowAny]
    authentication_classes = []

    @extend_schema(request=RestablecerContrasenaSerializer, responses={200: None})
    def post(self, request):
        datos = RestablecerContrasenaSerializer(data=request.data)
        datos.is_valid(raise_exception=True)
        datos.save()
        return Response(
            {"detail": "Tu contraseña se cambió. Ya puedes iniciar sesión con la nueva."},
            status=status.HTTP_200_OK,
        )
