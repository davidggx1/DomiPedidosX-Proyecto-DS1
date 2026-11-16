"""
HU-25 · El cliente cancela su pedido antes de que entre a preparación.

- Solo en "Pendiente de aprobación" o "Recibido" (criterios 1 y 2); la regla
  vive en la tabla TRANSICIONES de estados.py.
- En la misma transacción: cambia el estado (queda en el historial como
  "Cancelado", criterio 4) y devuelve el stock retenido (criterio 3).
- El cupo de la sede se libera solo: la capacidad cuenta los pedidos
  "recibido" y "en preparación", y el cupo de combos ignora los cancelados.
- El correo de cancelación lo envía pedidos/correos.py (HU-50) al cambiar el estado.

HU-33 · Cocina cancela un pedido por un error de cocina.

- Solo en "Recibido" o "En preparación" (tabla TRANSICIONES) y con una
  justificación obligatoria (criterio 1).
- El pedido queda "Cancelado" con el motivo "Cancelado por error de cocina: ...";
  se devuelve el stock y el cupo se libera solo, igual que en HU-25 (criterio 2).
- Avisa al cliente (notificación, su seguimiento en vivo y el correo de HU-50,
  que incluye el motivo) y al operador de la sede con un aviso en pantalla por
  WebSocket (criterio 3).
"""
import logging

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers, status
from rest_framework.response import Response
from rest_framework.views import APIView

from usuarios.permissions import EsCliente, EsCocina
from usuarios.roles import COCINA, nombre_para_mostrar

from .estados import CLIENTE, ESTADOS_FINALES, TransicionInvalida, cambiar_estado, siguientes_estados
from .models import EstadoPedido, Notificacion, TipoNotificacion
from .serializers import EstadoPedidoSerializer
from .stock import reintegrar_stock
from .consumers import grupo_sede
from .views import pedidos_visibles

logger = logging.getLogger(__name__)

MOTIVO_CLIENTE = "Cancelado por el cliente."


def cancelar_pedido_cliente(pedido, usuario):
    """Cancela el pedido del cliente, devuelve el stock y avisa. Lanza TransicionInvalida."""
    if pedido.estado not in ESTADOS_FINALES and EstadoPedido.CANCELADO not in siguientes_estados(
        pedido.estado, CLIENTE
    ):
        raise TransicionInvalida(
            f'Tu pedido ya está "{pedido.get_estado_display()}" y no se puede cancelar. '
            "Comunícate con la sede si necesitas ayuda.",
            "cancelacion_no_permitida",
        )

    with transaction.atomic():
        pedido = cambiar_estado(pedido, EstadoPedido.CANCELADO, usuario=usuario, rol=CLIENTE, motivo=MOTIVO_CLIENTE)
        reintegrar_stock(pedido)
        Notificacion.objects.create(
            usuario=usuario,
            pedido=pedido,
            mensaje=f"Cancelaste el pedido {pedido.numero_pedido}.",
            tipo=TipoNotificacion.PEDIDO_CANCELADO,
        )
    return pedido


class CancelarPedidoView(APIView):
    """POST /api/pedidos/<id>/cancelar/ · El cliente cancela su pedido (HU-25)."""

    permission_classes = [EsCliente]

    @extend_schema(request=None, responses=EstadoPedidoSerializer)
    def post(self, request, pk):
        pedido = get_object_or_404(
            pedidos_visibles(request.user, CLIENTE).select_related("cliente__usuario", "sede"), pk=pk
        )
        try:
            pedido = cancelar_pedido_cliente(pedido, request.user)
        except TransicionInvalida as error:
            return Response({"detail": error.mensaje, "codigo": error.codigo}, status=status.HTTP_400_BAD_REQUEST)
        pedido.refresh_from_db()
        return Response(EstadoPedidoSerializer(pedido, context={"rol": CLIENTE}).data)


# --- HU-33 · Cancelación por error de cocina --------------------------------------

PREFIJO_ERROR_COCINA = "Cancelado por error de cocina"
JUSTIFICACION_MINIMA = 5
JUSTIFICACION_MAXIMA = 500
TIPO_EVENTO_ERROR_COCINA = "pedido_cancelado_cocina"


def limpiar_justificacion(justificacion):
    """Devuelve la justificación sin espacios sobrantes. Lanza TransicionInvalida si no sirve."""
    texto = " ".join(str(justificacion or "").split())
    if not texto:
        raise TransicionInvalida("Escribe la justificación del error de cocina.", "motivo_obligatorio")
    if len(texto) < JUSTIFICACION_MINIMA:
        raise TransicionInvalida(
            f"La justificación debe tener al menos {JUSTIFICACION_MINIMA} caracteres.", "motivo_obligatorio"
        )
    if len(texto) > JUSTIFICACION_MAXIMA:
        raise TransicionInvalida(
            f"La justificación no puede superar {JUSTIFICACION_MAXIMA} caracteres.", "motivo_muy_largo"
        )
    return texto


def avisar_operador_error_cocina(pedido, usuario, justificacion):
    """Aviso en la pantalla del operador de la sede. Un fallo del canal no deshace nada."""
    evento = {
        "type": "pedido.evento",
        "data": {
            "tipo": TIPO_EVENTO_ERROR_COCINA,
            "pedido": {"id": pedido.pk, "numero_pedido": pedido.numero_pedido, "estado": pedido.estado},
            "justificacion": justificacion,
            "usuario_nombre": nombre_para_mostrar(usuario),
            "fecha_hora": timezone.localtime().isoformat(),
        },
    }
    try:
        async_to_sync(get_channel_layer().group_send)(grupo_sede(pedido.sede_id), evento)
    except Exception:
        logger.exception("No se pudo avisar al operador la cancelación del pedido %s", pedido.pk)


def cancelar_por_error_cocina(pedido, usuario, justificacion):
    """Cancela el pedido por error de cocina, devuelve el stock y avisa. Lanza TransicionInvalida."""
    justificacion = limpiar_justificacion(justificacion)
    motivo = f"{PREFIJO_ERROR_COCINA}: {justificacion}"

    with transaction.atomic():
        pedido = cambiar_estado(pedido, EstadoPedido.CANCELADO, usuario=usuario, rol=COCINA, motivo=motivo)
        reintegrar_stock(pedido)
        cliente = pedido.cliente
        if cliente is not None:
            # El correo al cliente, con el motivo, lo envía HU-50 (pedidos/correos.py) al cambiar el estado.
            Notificacion.objects.create(
                usuario=cliente.usuario,
                pedido=pedido,
                mensaje=f"Tu pedido {pedido.numero_pedido} fue cancelado por un error de cocina: {justificacion}",
                tipo=TipoNotificacion.PEDIDO_CANCELADO,
            )
        transaction.on_commit(lambda: avisar_operador_error_cocina(pedido, usuario, justificacion))
    return pedido


class CancelarErrorCocinaView(APIView):
    """POST /api/pedidos/<id>/cancelar-cocina/  {"justificacion": "..."} · HU-33."""

    permission_classes = [EsCocina]

    @extend_schema(
        request=inline_serializer("CancelarErrorCocina", {"justificacion": serializers.CharField()}),
        responses=EstadoPedidoSerializer,
    )
    def post(self, request, pk):
        pedido = get_object_or_404(
            pedidos_visibles(request.user, COCINA).select_related("cliente__usuario", "sede"), pk=pk
        )
        try:
            pedido = cancelar_por_error_cocina(pedido, request.user, request.data.get("justificacion"))
        except TransicionInvalida as error:
            campo = "justificacion" if error.codigo in ("motivo_obligatorio", "motivo_muy_largo") else "detail"
            return Response({campo: error.mensaje, "codigo": error.codigo}, status=status.HTTP_400_BAD_REQUEST)
        pedido.refresh_from_db()
        return Response(EstadoPedidoSerializer(pedido, context={"rol": COCINA}).data)
