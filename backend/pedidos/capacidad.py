"""
Automatic block by capacity (HU-61)

A sede has a limit of simultaneous orders per time slot (CapacidadSede, HU-59).
Every new order, from the web or from the operator, goes through
validar_cupo_nuevo_pedido before it is created.

- Orders that use a slot: pendiente_aprobacion, recibido and en_preparacion.
  When an order moves to listo_despacho or cancelado it stops counting, so the
  slot is released and new orders are accepted again
- The block only stops NEW orders. The kitchen keeps moving the accepted ones
  because estados.py does not call this module
- Without a slot for the current day and hour the check cannot be done: the
  customer is rejected and the operator gets a warning to confirm by hand
"""
from django.utils import timezone
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from sedes.models import CapacidadSede, Sede
from usuarios.roles import ADMINISTRADOR, OPERADOR, obtener_rol, obtener_sede

from .models import EstadoPedido, Pedido

DIAS = ["lunes", "martes", "miercoles", "jueves", "viernes", "sabado", "domingo"]

ESTADOS_QUE_OCUPAN_CUPO = (
    EstadoPedido.PENDIENTE_APROBACION,
    EstadoPedido.RECIBIDO,
    EstadoPedido.EN_PREPARACION,
)

DISPONIBLE = "disponible"
SATURADA = "saturada"
SIN_FRANJA = "sin_franja"


class ErrorCapacidad(ValidationError):
    """409 with the state of the sede, so the front can show a dynamic message."""

    status_code = 409
    default_code = "capacidad"

    def __init__(self, estado, codigo):
        self.detail = {"detail": estado["mensaje"], "codigo": codigo, **estado}


def franja_actual(sede, ahora=None):
    """CapacidadSede of the sede for the current day and hour, or None."""
    ahora = ahora or timezone.localtime()
    dia = DIAS[ahora.weekday()]
    franjas = CapacidadSede.objects.filter(
        sede=sede, hora_inicio__lte=ahora.time(), hora_fin__gte=ahora.time()
    )
    for franja in franjas:
        dias = [d.strip().lower() for d in franja.dias_semana.split(",") if d.strip()]
        if dia in dias:
            return franja
    return None


def pedidos_que_ocupan_cupo(sede):
    return Pedido.objects.filter(sede=sede, estado__in=ESTADOS_QUE_OCUPAN_CUPO).count()


def estado_capacidad(sede, *, puede_confirmar_manual=False, ahora=None):
    """
    Current capacity of the sede, ready to send to the front.

    `puede_confirmar_manual` is True for staff (operator, admin): without a slot
    they are warned and can confirm by hand. A customer cannot, so it is blocked.
    """
    franja = franja_actual(sede, ahora)
    activos = pedidos_que_ocupan_cupo(sede)
    base = {
        "sede": sede.pk,
        "activos": activos,
        "maximo": None,
        "porcentaje": None,
        "umbral_alerta": None,
        "en_alerta": False,
        "requiere_confirmacion": False,
    }

    if franja is None:
        if puede_confirmar_manual:
            mensaje = (
                f"La sede {sede.nombre} no tiene una franja de capacidad configurada "
                "para este día y hora. Puedes confirmar el pedido de todas formas."
            )
        else:
            mensaje = (
                f"No pudimos validar la capacidad de la sede {sede.nombre} en este "
                "horario porque no tiene una franja configurada. Intenta más tarde."
            )
        return {
            **base,
            "estado": SIN_FRANJA,
            "bloqueado": not puede_confirmar_manual,
            "requiere_confirmacion": puede_confirmar_manual,
            "mensaje": mensaje,
        }

    maximo = franja.max_pedidos_simultaneos
    base.update(
        maximo=maximo,
        porcentaje=min(100, round(activos * 100 / maximo)),
        umbral_alerta=franja.umbral_alerta,
        en_alerta=activos >= franja.umbral_alerta,
    )

    if activos >= maximo:
        return {
            **base,
            "estado": SATURADA,
            "bloqueado": True,
            "mensaje": (
                f"La sede {sede.nombre} alcanzó el 100% de su capacidad "
                f"({activos}/{maximo}). No recibe nuevos pedidos por ahora, "
                "intenta de nuevo en unos minutos."
            ),
        }

    return {
        **base,
        "estado": DISPONIBLE,
        "bloqueado": False,
        "mensaje": f"Cupos disponibles: {maximo - activos} de {maximo}.",
    }


def validar_cupo_nuevo_pedido(
    sede, *, puede_confirmar_manual=False, confirmado_sin_franja=False, ahora=None
):
    """
    Raises ErrorCapacidad if a new order cannot enter. Call it inside the same
    transaction that creates the order.

    The sede row is locked until that transaction ends, so two orders that arrive
    at the same time cannot both take the last slot.
    """
    Sede.objects.select_for_update().get(pk=sede.pk)

    estado = estado_capacidad(
        sede, puede_confirmar_manual=puede_confirmar_manual, ahora=ahora
    )

    if estado["estado"] == SATURADA:
        raise ErrorCapacidad(estado, "capacidad_maxima_alcanzada")

    if estado["estado"] == SIN_FRANJA and not (
        puede_confirmar_manual and confirmado_sin_franja
    ):
        raise ErrorCapacidad(estado, "franja_no_configurada")

    return estado


class EstadoCapacidadView(APIView):
    """
    GET /api/pedidos/capacidad/?sede=<id>

    The front uses it to disable the confirm button before the order is sent.
    The operator always sees his own sede. Customers and admins send ?sede=<id>.
    """

    permission_classes = [IsAuthenticated]

    @extend_schema(
        parameters=[OpenApiParameter("sede", int, required=False)],
        responses={200: None},
    )
    def get(self, request):
        rol = obtener_rol(request.user)
        es_cliente = rol is None and hasattr(request.user, "cliente")
        if not es_cliente and rol not in (OPERADOR, ADMINISTRADOR):
            return Response(
                {"detail": "No tienes permiso para consultar la capacidad."},
                status=status.HTTP_403_FORBIDDEN,
            )

        if rol == OPERADOR:
            sede = obtener_sede(request.user)
            if sede is None:
                return Response(
                    {"detail": "El operador no tiene una sede asignada."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        else:
            sede_id = request.query_params.get("sede")
            if not sede_id or not sede_id.isdigit():
                return Response(
                    {"detail": "Indica la sede con ?sede=<id>."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            sede = Sede.objects.filter(pk=int(sede_id), activa=True).first()
            if sede is None:
                return Response(
                    {"detail": "La sede no existe o no está activa."},
                    status=status.HTTP_404_NOT_FOUND,
                )

        return Response(estado_capacidad(sede, puede_confirmar_manual=not es_cliente))
