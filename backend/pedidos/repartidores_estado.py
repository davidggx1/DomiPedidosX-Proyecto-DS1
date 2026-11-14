"""
HU-37 · Estado logístico de los repartidores de la sede.

Un solo endpoint devuelve, por repartidor, su estado ("disponible", "no_disponible" o
"en_entrega"), su carga de trabajo y los pedidos que lleva con su avance. Cuando algo
cambia (asignación, estado de un pedido o disponibilidad) se avisa por WebSocket y el
tablero vuelve a pedir la lista: el aviso no trae datos, igual que en HU-42.
"""
import logging

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.db.models import Prefetch
from drf_spectacular.utils import extend_schema
from rest_framework import generics, serializers

from usuarios.models import Repartidor
from usuarios.permissions import filtrar_por_sede, rol_requerido
from usuarios.roles import ADMINISTRADOR, OPERADOR

from .asignacion import ESTADOS_EN_CURSO
from .consumers import GRUPO_ADMIN_REPARTIDORES, grupo_repartidores_sede
from .models import EstadoPedido, Pedido

logger = logging.getLogger(__name__)

DISPONIBLE = "disponible"
NO_DISPONIBLE = "no_disponible"
EN_ENTREGA = "en_entrega"

# Pasos de una entrega, en orden. El avance de un pedido es su posición aquí.
PASOS_ENTREGA = (
    EstadoPedido.LISTO_DESPACHO,
    EstadoPedido.RECOGIDO,
    EstadoPedido.EN_CAMINO,
    EstadoPedido.ENTREGADO,
)


def estado_logistico(disponible, pedidos_activos):
    """Con pedidos en curso está "En entrega", aunque se haya puesto "No disponible"
    (HU-41, criterio 3: pasar a No disponible no le quita lo que ya tiene asignado)."""
    if pedidos_activos > 0:
        return EN_ENTREGA
    return DISPONIBLE if disponible else NO_DISPONIBLE


def avance_pedido(estado):
    """{ paso, total }: paso 0 si el estado no es parte del recorrido de entrega."""
    pasos = [paso.value for paso in PASOS_ENTREGA]
    return {"paso": pasos.index(estado) + 1 if estado in pasos else 0, "total": len(pasos)}


def avisar_estado_repartidores(sede_id):
    """Dice a los tableros (operador de la sede y administrador) que vuelvan a pedir la lista.

    Un fallo del canal nunca debe romper la asignación, el cambio de estado ni el login.
    """
    grupos = [GRUPO_ADMIN_REPARTIDORES]
    if sede_id is not None:
        grupos.append(grupo_repartidores_sede(sede_id))
    evento = {"type": "repartidores.evento", "data": {"tipo": "repartidores_actualizados"}}
    try:
        capa = get_channel_layer()
        for grupo in grupos:
            async_to_sync(capa.group_send)(grupo, evento)
    except Exception:
        logger.exception("No se pudo avisar el estado de los repartidores (sede %s)", sede_id)


class PedidoAsignadoSerializer(serializers.ModelSerializer):
    estado_nombre = serializers.CharField(source="get_estado_display", read_only=True)
    avance = serializers.SerializerMethodField()

    class Meta:
        model = Pedido
        fields = [
            "id",
            "numero_pedido",
            "estado",
            "estado_nombre",
            "avance",
            "entrega_direccion",
            "entrega_barrio",
            "tiempo_estimado_entrega",
            "fecha_creacion",
        ]

    def get_avance(self, pedido):
        return avance_pedido(pedido.estado)


class RepartidorEstadoSerializer(serializers.ModelSerializer):
    nombres = serializers.CharField(source="empleado.nombres", read_only=True)
    apellidos = serializers.CharField(source="empleado.apellidos", read_only=True)
    celular = serializers.CharField(source="empleado.celular", read_only=True)
    sede_id = serializers.IntegerField(source="empleado.sede_id", read_only=True)
    estado = serializers.SerializerMethodField()
    estado_nombre = serializers.SerializerMethodField()
    carga = serializers.SerializerMethodField()
    pedidos = PedidoAsignadoSerializer(source="pedidos_en_curso", many=True, read_only=True)

    class Meta:
        model = Repartidor
        fields = [
            "id",
            "nombres",
            "apellidos",
            "celular",
            "sede_id",
            "disponible",
            "estado",
            "estado_nombre",
            "carga",
            "pedidos",
        ]

    def get_carga(self, repartidor):
        return len(repartidor.pedidos_en_curso)

    def get_estado(self, repartidor):
        return estado_logistico(repartidor.disponible, self.get_carga(repartidor))

    def get_estado_nombre(self, repartidor):
        return NOMBRE_ESTADO[self.get_estado(repartidor)]


NOMBRE_ESTADO = {
    DISPONIBLE: "Disponible",
    NO_DISPONIBLE: "No disponible",
    EN_ENTREGA: "En entrega",
}


@extend_schema(responses=RepartidorEstadoSerializer(many=True))
class EstadoRepartidoresView(generics.ListAPIView):
    """
    GET /api/pedidos/repartidores/estado/

    HU-37: repartidores activos con su estado logístico, su carga y los pedidos que
    llevan (con su avance). El operador ve solo los de su sede; el administrador, todos.
    """

    serializer_class = RepartidorEstadoSerializer
    permission_classes = [rol_requerido(OPERADOR, ADMINISTRADOR)]
    pagination_class = None

    def get_queryset(self):
        en_curso = Prefetch(
            "pedidos_asignados",
            queryset=Pedido.objects.filter(estado__in=ESTADOS_EN_CURSO).order_by("fecha_creacion", "id"),
            to_attr="pedidos_en_curso",
        )
        repartidores = (
            Repartidor.objects.filter(empleado__usuario__is_active=True)
            .select_related("empleado")
            .prefetch_related(en_curso)
            .order_by("empleado__nombres", "empleado__apellidos", "id")
        )
        return filtrar_por_sede(repartidores, self.request.user, campo="empleado__sede")