from django.db.models import OuterRef, Prefetch, Subquery
from django.db.models.functions import Coalesce
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiParameter, extend_schema, inline_serializer
from rest_framework import status
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from usuarios.roles import ADMINISTRADOR, COCINA, OPERADOR, REPARTIDOR, obtener_rol, obtener_sede

from .estados import CLIENTE, TransicionInvalida, cambiar_estado
from .models import EstadoPedido, HistorialEstadoPedido, Pedido
from .serializers import (
    CambioEstadoSerializer,
    ComandaCocinaSerializer,
    EstadoPedidoSerializer,
    TarjetaCocinaSerializer,
)


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


# --- Cocina: tablero Kanban (HU-29) y comanda (HU-30) ----------------------------

COLUMNAS_COCINA = [EstadoPedido.RECIBIDO, EstadoPedido.EN_PREPARACION, EstadoPedido.LISTO_DESPACHO]
ROLES_COCINA = (COCINA, OPERADOR, ADMINISTRADOR)


def momento_del_estado(estado):
    """Primera vez que el pedido llegó a `estado`, según el historial."""
    return Subquery(
        HistorialEstadoPedido.objects.filter(pedido=OuterRef("pk"), estado=estado)
        .order_by("fecha_hora")
        .values("fecha_hora")[:1]
    )


def pedidos_para_cocina(usuario, rol):
    """Pedidos visibles con la hora de entrada a cocina y todo lo necesario para la comanda."""
    return (
        pedidos_visibles(usuario, rol)
        .annotate(
            # Si no hay historial (pedido creado ya "recibido"), se usa la fecha de creación.
            recibido_en=Coalesce(momento_del_estado(EstadoPedido.RECIBIDO), "fecha_creacion"),
            listo_en=momento_del_estado(EstadoPedido.LISTO_DESPACHO),
        )
        .prefetch_related(
            "detalles__producto",
            "detalles__producto_tamano",
            "detalles__combo",
            "detalles__adiciones__adicion",
            "detalles__exclusiones",
        )
    )


def rol_de_cocina(usuario):
    rol = rol_de(usuario)
    if rol not in ROLES_COCINA:
        raise PermissionDenied("Solo cocina, el operador o el administrador ven la cocina.")
    return rol


class TableroCocinaView(APIView):
    """
    GET /api/pedidos/cocina/tablero/

    Pedidos de la sede en tres columnas: recibido, en preparación y listo para
    despacho, del más antiguo al más nuevo (HU-29 y HU-32). Cocina y operador
    ven solo su sede; el administrador puede filtrar con ?sede=<id>.
    """

    permission_classes = [IsAuthenticated]

    @extend_schema(
        parameters=[OpenApiParameter("sede", int, description="Solo administrador: filtrar por sede.")],
        responses=inline_serializer(
            "TableroCocina",
            {estado.value: TarjetaCocinaSerializer(many=True) for estado in COLUMNAS_COCINA},
        ),
    )
    def get(self, request):
        rol = rol_de_cocina(request.user)
        pedidos = pedidos_para_cocina(request.user, rol).filter(estado__in=COLUMNAS_COCINA)

        sede = request.query_params.get("sede")
        if sede is not None and rol == ADMINISTRADOR:
            if not sede.isdigit():
                return Response(
                    {"sede": "Debe ser el id numérico de una sede."}, status=status.HTTP_400_BAD_REQUEST
                )
            pedidos = pedidos.filter(sede_id=int(sede))

        pedidos = pedidos.order_by("recibido_en", "id")
        contexto = {"rol": rol}
        tablero = {estado.value: [] for estado in COLUMNAS_COCINA}
        for pedido in pedidos:
            tablero[pedido.estado].append(TarjetaCocinaSerializer(pedido, context=contexto).data)
        return Response(tablero)


class ComandaCocinaView(APIView):
    """
    GET /api/pedidos/<id>/cocina/

    Detalle para preparar el pedido (HU-30): platos, cantidades, tamaños,
    adiciones, ingredientes quitados ("sin") y notas del cliente.
    """

    permission_classes = [IsAuthenticated]

    @extend_schema(responses=ComandaCocinaSerializer)
    def get(self, request, pk):
        rol = rol_de_cocina(request.user)
        pedido = get_object_or_404(pedidos_para_cocina(request.user, rol), pk=pk)
        return Response(ComandaCocinaSerializer(pedido, context={"rol": rol}).data)
