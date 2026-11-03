from drf_spectacular.utils import extend_schema
from rest_framework import status, permissions
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView
from sedes.views import EsAdministradorPermission
from .models import Empleado

from .serializers import LoginSerializer, RegistroClienteSerializer, RegistroEmpleadoSerializer, EmpleadoListSerializer
from .permissions import rol_requerido
from .roles import ROLES_PERSONAL, obtener_rol, obtener_sede
from .serializers import LoginPersonalSerializer


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

class EmpleadoManagementView(APIView):
    permission_classes = [permissions.IsAuthenticated, EsAdministradorPermission]

    @extend_schema(responses={200: EmpleadoListSerializer(many=True)})
    def get(self, request):
        """Listado de personal con filtros por rol y sede."""
        queryset = Empleado.objects.select_related("usuario", "sede").all()

        rol = request.query_params.get("rol")
        sede_id = request.query_params.get("sede")

        if rol:
            queryset = queryset.filter(usuario__groups__name=rol)
        if sede_id:
            queryset = queryset.filter(sede_id=sede_id)

        serializer = EmpleadoListSerializer(queryset, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @extend_schema(request=RegistroEmpleadoSerializer, responses={201: None})
    def post(self, request):
        """Registro de nuevo empleado."""
        serializer = RegistroEmpleadoSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        empleado = serializer.save()

        return Response(
            {
                "detail": "Empleado registrado correctamente.",
                "email": empleado.usuario.email,
                "contrasena_inicial": getattr(empleado, "contrasena_inicial", None),
            },
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