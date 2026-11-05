from django.db.models import Prefetch
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from usuarios.roles import ADMINISTRADOR, COCINA, OPERADOR, REPARTIDOR, obtener_rol, obtener_sede

from .estados import CLIENTE, TransicionInvalida, cambiar_estado
from .models import HistorialEstadoPedido, Pedido
from .serializers import CambioEstadoSerializer, EstadoPedidoSerializer


def rol_de(usuario):
    """Rol de personal del usuario, "cliente" si tiene perfil de cliente, o None."""
    rol = obtener_rol(usuario)
    if rol is None and hasattr(usuario, "cliente"):
        return CLIENTE
    return rol


def pedidos_visibles(usuario, rol):
    """
    Pedidos que puede ver y mover cada rol:
    administrador todos; operador y cocina los de su sede;
    repartidor los asignados a él; cliente los suyos.
    """
    pedidos = Pedido.objects.all()
    if rol == ADMINISTRADOR:
        return pedidos
    if rol in (OPERADOR, COCINA):
        sede = obtener_sede(usuario)
        return pedidos.filter(sede=sede) if sede else pedidos.none()
    if rol == REPARTIDOR:
        return pedidos.filter(repartidor__empleado__usuario=usuario)
    if rol == CLIENTE:
        return pedidos.filter(cliente__usuario=usuario)
    return pedidos.none()


class EstadoPedidoView(APIView):
    """
    GET   /api/pedidos/<id>/estado/  → estado actual, historial y siguientes estados posibles.
    PATCH /api/pedidos/<id>/estado/  → {"estado": "en_preparacion", "motivo": ""}

    Un pedido de otra sede (o ajeno) responde 404. Las reglas del cambio
    viven en pedidos/estados.py.
    """

    permission_classes = [IsAuthenticated]

    def obtener(self, request, pk):
        rol = rol_de(request.user)
        if rol is None:
            raise PermissionDenied("Tu cuenta no tiene un rol asignado.")
        historial = HistorialEstadoPedido.objects.select_related("usuario").order_by("fecha_hora", "id")
        pedido = get_object_or_404(
            pedidos_visibles(request.user, rol).prefetch_related(Prefetch("historial_estados", historial)),
            pk=pk,
        )
        return pedido, rol

    def responder(self, pedido, rol):
        return Response(EstadoPedidoSerializer(pedido, context={"rol": rol}).data)

    @extend_schema(responses=EstadoPedidoSerializer)
    def get(self, request, pk):
        pedido, rol = self.obtener(request, pk)
        return self.responder(pedido, rol)

    @extend_schema(request=CambioEstadoSerializer, responses=EstadoPedidoSerializer)
    def patch(self, request, pk):
        pedido, rol = self.obtener(request, pk)
        datos = CambioEstadoSerializer(data=request.data)
        datos.is_valid(raise_exception=True)

        try:
            cambiar_estado(
                pedido,
                datos.validated_data["estado"],
                usuario=request.user,
                rol=rol,
                motivo=datos.validated_data.get("motivo", ""),
            )
        except TransicionInvalida as error:
            campo = "motivo" if error.codigo == "motivo_obligatorio" else "detail"
            codigo_http = (
                status.HTTP_403_FORBIDDEN
                if error.codigo == "rol_no_autorizado"
                else status.HTTP_400_BAD_REQUEST
            )
            return Response({campo: error.mensaje, "codigo": error.codigo}, status=codigo_http)

        pedido, rol = self.obtener(request, pk)
        return self.responder(pedido, rol)
