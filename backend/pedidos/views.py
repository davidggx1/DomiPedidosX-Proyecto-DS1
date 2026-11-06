from django.db.models import OuterRef, Prefetch, Subquery
from django.db.models.functions import Coalesce
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiParameter, extend_schema, inline_serializer
from rest_framework import status
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.generics import ListAPIView

from rest_framework.permissions import BasePermission
from .serializers_confirmar import ConfirmarPedidoSerializer


from usuarios.models import Repartidor
from usuarios.roles import ADMINISTRADOR, COCINA, OPERADOR, REPARTIDOR, obtener_rol, obtener_sede
from usuarios.permissions import filtrar_por_sede, rol_requerido

from .asignacion import AsignacionInvalida, asignar, retirar
from .estados import CLIENTE, TransicionInvalida, cambiar_estado
from .models import EstadoPedido, HistorialEstadoPedido, OrigenPedido, Pedido
from .serializers import (
    AsignarRepartidorSerializer,
    CambioEstadoSerializer,
    ComandaCocinaSerializer,
    EstadoPedidoSerializer,
    PedidoDespachoSerializer,
    TarjetaCocinaSerializer,
    PedidoEntranteSerializer, 
    pedidos_con_detalle,
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


# --- Despacho: asignación manual de repartidor (HU-35) ---------------------------

ROLES_DESPACHO = (OPERADOR, ADMINISTRADOR)


def rol_de_despacho(usuario):
    rol = rol_de(usuario)
    if rol not in ROLES_DESPACHO:
        raise PermissionDenied("Solo el operador o el administrador asignan repartidores.")
    return rol


class DespachoView(APIView):
    """
    GET /api/pedidos/despacho/

    Pedidos "Listo para despacho" que van a domicilio, del más antiguo al más
    nuevo, con su repartidor si ya tienen uno. Junto con
    GET /api/usuarios/repartidores/?disponible=true forma las dos listas del
    módulo de logística (HU-35, criterio 1). El administrador puede filtrar
    con ?sede=<id>.
    """

    permission_classes = [IsAuthenticated]

    @extend_schema(
        parameters=[OpenApiParameter("sede", int, description="Solo administrador: filtrar por sede.")],
        responses=PedidoDespachoSerializer(many=True),
    )
    def get(self, request):
        rol = rol_de_despacho(request.user)
        pedidos = (
            pedidos_visibles(request.user, rol)
            .filter(estado=EstadoPedido.LISTO_DESPACHO)
            .exclude(origen=OrigenPedido.MOSTRADOR)
            .annotate(listo_en=momento_del_estado(EstadoPedido.LISTO_DESPACHO))
            .select_related("repartidor__empleado")
            .prefetch_related("detalles__producto", "detalles__producto_tamano", "detalles__combo")
        )
        sede = request.query_params.get("sede")
        if sede is not None and rol == ADMINISTRADOR:
            if not sede.isdigit():
                return Response(
                    {"sede": "Debe ser el id numérico de una sede."}, status=status.HTTP_400_BAD_REQUEST
                )
            pedidos = pedidos.filter(sede_id=int(sede))
        pedidos = pedidos.order_by("listo_en", "id")
        return Response(PedidoDespachoSerializer(pedidos, many=True).data)


class AsignacionRepartidorView(APIView):
    """
    POST   /api/pedidos/<id>/repartidor/  {"repartidor": <id>}  → asigna.
    DELETE /api/pedidos/<id>/repartidor/                      → retira la asignación.

    Las reglas viven en pedidos/asignacion.py.
    """

    permission_classes = [IsAuthenticated]

    def obtener_pedido(self, request, pk):
        rol = rol_de_despacho(request.user)
        return get_object_or_404(pedidos_visibles(request.user, rol), pk=pk)

    def responder(self, pedido):
        pedido = (
            Pedido.objects.filter(pk=pedido.pk)
            .annotate(listo_en=momento_del_estado(EstadoPedido.LISTO_DESPACHO))
            .select_related("repartidor__empleado")
            .prefetch_related("detalles__producto", "detalles__producto_tamano", "detalles__combo")
            .get()
        )
        return Response(PedidoDespachoSerializer(pedido).data)

    @staticmethod
    def error(error):
        codigo_http = status.HTTP_409_CONFLICT if error.codigo == "pedido_ya_asignado" else status.HTTP_400_BAD_REQUEST
        return Response({error.campo: error.mensaje, "codigo": error.codigo}, status=codigo_http)

    @extend_schema(request=AsignarRepartidorSerializer, responses=PedidoDespachoSerializer)
    def post(self, request, pk):
        pedido = self.obtener_pedido(request, pk)
        datos = AsignarRepartidorSerializer(data=request.data)
        datos.is_valid(raise_exception=True)
        repartidor = Repartidor.objects.filter(pk=datos.validated_data["repartidor"]).first()
        if repartidor is None:
            return Response(
                {"repartidor": "El repartidor no existe.", "codigo": "repartidor_inexistente"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            pedido = asignar(pedido, repartidor, usuario=request.user)
        except AsignacionInvalida as error:
            return self.error(error)
        return self.responder(pedido)

    @extend_schema(request=None, responses=PedidoDespachoSerializer)
    def delete(self, request, pk):
        pedido = self.obtener_pedido(request, pk)
        try:
            pedido = retirar(pedido, usuario=request.user)
        except AsignacionInvalida as error:
            return self.error(error)
        return self.responder(pedido)


class PedidosEntrantesView(ListAPIView):
    """Pedidos pendientes de aprobación, del más antiguo al más nuevo, solo de la sede del usuario."""

    serializer_class = PedidoEntranteSerializer
    permission_classes = [rol_requerido(OPERADOR, ADMINISTRADOR)]

    def get_queryset(self):
        qs = pedidos_con_detalle().filter(estado=EstadoPedido.PENDIENTE_APROBACION)
        return filtrar_por_sede(qs, self.request.user).order_by("fecha_creacion", "id")



class EsCliente(BasePermission):
    message = "Solo los clientes pueden confirmar pedidos."

    def has_permission(self, request, view):
        usuario = request.user
        return bool(usuario and usuario.is_authenticated and hasattr(usuario, "cliente"))


class ConfirmarPedidoView(APIView):
    """HU-23: el carrito viaja en el cuerpo; el servidor recalcula los precios."""

    permission_classes = [EsCliente]

    @extend_schema(request=ConfirmarPedidoSerializer, responses={201: None})
    def post(self, request):
        from .servicios import confirmar_pedido  # evita import circular con consumers
        serializer = ConfirmarPedidoSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        pedido, factura = confirmar_pedido(
            usuario=request.user,
            cliente=request.user.cliente,
            datos=serializer.validated_data,
        )
        return Response(
            {
                "id": pedido.pk,
                "numero_pedido": pedido.numero_pedido,
                "estado": pedido.estado,
                "tiempo_estimado_entrega": pedido.tiempo_estimado_entrega,
                "factura": {
                    "numero": factura.numero,
                    "subtotal": factura.subtotal,
                    "iva": factura.iva,
                    "costo_domicilio": factura.costo_domicilio,
                    "total": factura.total,
                    "metodo_pago": factura.metodo_pago,
                    "estado": factura.estado_factura,
                },
            },
            status=status.HTTP_201_CREATED,
        )



class AprobarPedidoView(APIView):
    """HU-28: el operador aprueba un pedido entrante (pendiente -> recibido)."""

    permission_classes = [rol_requerido(OPERADOR, ADMINISTRADOR)]

    @extend_schema(request=None, responses={200: None})
    def patch(self, request, pk):
        # Import perezoso: evita el import circular con consumers (como en HU-23).
        from .aprobacion import aprobar_pedido

        pedido, registro = aprobar_pedido(usuario=request.user, pedido_id=pk)
        return Response(
            {
                "id": pedido.pk,
                "numero_pedido": pedido.numero_pedido,
                "estado": pedido.estado,
                "aprobado_por": request.user.email,
                "fecha_aprobacion": registro.fecha_hora,
            }
        )