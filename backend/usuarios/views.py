from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView

from .permissions import rol_requerido
from .roles import ROLES_PERSONAL, obtener_rol, obtener_sede
from .serializers import LoginPersonalSerializer, LoginSerializer, RegistroClienteSerializer


class RegistroClienteView(APIView):
    # Público: el default del proyecto exige estar autenticado.
    permission_classes = [AllowAny]
    authentication_classes = []

    @extend_schema(request=RegistroClienteSerializer, responses={201: None})
    def post(self, request):
        serializer = RegistroClienteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        cliente = serializer.save()
        return Response(
            {"detail": "Cuenta creada correctamente.", "email": cliente.usuario.email},
            status=status.HTTP_201_CREATED,
        )

class LoginView(TokenObtainPairView):
    serializer_class = LoginSerializer

class LoginPersonalView(TokenObtainPairView):
    serializer_class = LoginPersonalSerializer


class PerfilPersonalView(APIView):
    """Rol y sede del usuario autenticado; el frontend lo usa para armar el menú."""

    permission_classes = [rol_requerido(*ROLES_PERSONAL)]

    @extend_schema(responses={200: None})
    def get(self, request):
        sede = obtener_sede(request.user)
        return Response(
            {
                "email": request.user.email,
                "rol": obtener_rol(request.user),
                "sede_id": sede.pk if sede else None,
            }
        )