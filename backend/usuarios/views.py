from drf_spectacular.utils import extend_schema
from rest_framework import generics, permissions, status, viewsets
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView
from sedes.views import EsAdministradorPermission
from .models import DireccionEntrega, Empleado

from .serializers import LoginSerializer, RegistroClienteSerializer, RegistroEmpleadoSerializer, EmpleadoListSerializer
from .permissions import EsCliente, rol_requerido
from .roles import ROLES_PERSONAL, obtener_rol, obtener_sede
from .serializers import DireccionEntregaSerializer, LoginPersonalSerializer, PerfilClienteSerializer


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


class PerfilClienteView(generics.RetrieveUpdateAPIView):
    """
    GET / PATCH /api/usuarios/perfil/

    HU-07: el cliente consulta y edita sus nombres, apellidos y celular.
    Si cambia el celular, se vuelve a validar con las reglas del registro.
    """

    serializer_class = PerfilClienteSerializer
    permission_classes = [EsCliente]
    http_method_names = ["get", "patch", "head", "options"]

    def get_object(self):
        return self.request.user.cliente


class DireccionEntregaViewSet(viewsets.ModelViewSet):
    """HU-06: el cliente gestiona solo sus direcciones. Eliminar es borrado lógico."""

    serializer_class = DireccionEntregaSerializer
    permission_classes = [EsCliente]
    http_method_names = ["get", "post", "patch", "delete"]

    def get_queryset(self):
        # Las ajenas no aparecen: responden 404 sin revelar que existen.
        return DireccionEntrega.objects.filter(
            cliente=self.request.user.cliente, activa=True
        ).order_by("-es_principal", "alias", "id")

    def perform_destroy(self, instance):
        # Los pedidos guardan su propia copia de la dirección, así que no cambian.
        instance.activa = False
        instance.es_principal = False
        instance.save(update_fields=["activa", "es_principal"])
