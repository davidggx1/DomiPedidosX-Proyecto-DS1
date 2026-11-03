from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView

from .serializers import LoginSerializer, RegistroClienteSerializer


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