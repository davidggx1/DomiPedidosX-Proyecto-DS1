"""
HU-83 · Notificaciones de la sede.

El administrador elige, por sede y por evento, quién recibe un correo:
- un rol: todo el personal ACTIVO con ese rol en esa sede (los administradores
  no tienen sede, así que el rol "administrador" son todos los administradores);
- un correo suelto, aunque no sea una cuenta del sistema (p. ej. el gerente).

Eventos (EventoSede):
- stock_bajo:  se crea una alerta de inventario (HU-16), en inventario/alertas.py
- cancelacion: un pedido de la sede pasa a "Cancelado" (cliente, sede o el
               sistema), en pedidos/signals.py
- sobrecupo:   la sede llega al umbral de alerta de su franja (HU-60), en
               pedidos/alertas_capacidad.py

Los avisos por WebSocket que ya existían no cambian: esto solo agrega el correo.
Si nadie está suscrito no se envía nada. Un fallo aquí nunca rompe la acción que
causó el evento (un pedido, un descuento de stock...): solo queda en el log.

API (solo administrador):
    GET    /api/notificaciones-sede/?sede=<id>   suscripciones de una sede
    POST   /api/notificaciones-sede/             {sede, evento, rol} o {sede, evento, correo}
    DELETE /api/notificaciones-sede/<id>/
"""
import logging

from django.db.models import Q
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema, extend_schema_view
from rest_framework import mixins, serializers, viewsets

from .models import EventoSede, RolSuscrito, Sede, SuscripcionNotificacion

logger = logging.getLogger(__name__)


# --- Envío ---------------------------------------------------------------------


def destinatarios(sede_id, evento):
    """Correos (sin repetir, en orden) que deben recibir este evento de la sede."""
    # Importado aquí: usuarios depende de sedes, no al revés.
    from usuarios.models import Usuario

    suscripciones = SuscripcionNotificacion.objects.filter(sede_id=sede_id, evento=evento)
    correos = {s.correo.lower() for s in suscripciones if s.correo}

    filtro_roles = Q()
    for rol in {s.rol for s in suscripciones if s.rol}:
        if rol == RolSuscrito.ADMINISTRADOR:
            filtro_roles |= Q(groups__name=rol)
        else:
            filtro_roles |= Q(groups__name=rol, empleado__sede_id=sede_id)
    if filtro_roles:
        personal = Usuario.objects.filter(filtro_roles, is_active=True).exclude(email="")
        correos |= {email.lower() for email in personal.values_list("email", flat=True)}

    return sorted(correos)


def notificar_evento_sede(sede_id, evento, asunto, mensaje):
    """
    Envía el aviso a los suscritos de la sede. Devuelve a cuántos se envió.

    Un correo por destinatario, para que nadie vea los correos de los demás.
    Llamar después del commit (transaction.on_commit), para no avisar de algo
    que al final no se guardó.
    """
    from usuarios.tasks import encolar_correo

    try:
        lista = destinatarios(sede_id, evento)
        if not lista:
            return 0
        sede = Sede.objects.get(pk=sede_id)
        cuerpo = f"{mensaje}\n\nRecibes este correo porque estás suscrito a los avisos de {sede.nombre}.\n\nDomiPedidosX"
        for correo in lista:
            encolar_correo(f"[{sede.nombre}] {asunto}", cuerpo, [correo])
        return len(lista)
    except Exception:
        logger.exception("No se pudo enviar el aviso %s de la sede %s", evento, sede_id)
        return 0


# --- Textos de cada evento ---------------------------------------------------------


def _cantidad(valor):
    if valor is None:
        return "?"
    return f"{valor:g}" if isinstance(valor, float) else str(valor)


def avisar_stock_bajo(alerta):
    """`alerta` es el dict de inventario.alertas.datos_alerta."""
    unidad = alerta["unidad"]
    unidades = "unidades" if unidad == "unidad" else unidad
    notificar_evento_sede(
        alerta["sede"],
        EventoSede.STOCK_BAJO,
        f"Stock bajo: {alerta['nombre']}",
        f"El {alerta['tipo']} \"{alerta['nombre']}\" quedó en {_cantidad(alerta['stock_actual'])} {unidades}, "
        f"igual o por debajo del mínimo de {_cantidad(alerta['stock_minimo'])}.\n"
        "Revisa el inventario de la sede para reponerlo.",
    )


QUIEN_CANCELA = {
    "administrador": "por un administrador",
    "operador": "por el operador de la sede",
    "cocina": "por la cocina de la sede",
    "repartidor": "por el repartidor",
}


def avisar_cancelacion(pedido, usuario):
    """`usuario` es quien canceló; None si fue el sistema (p. ej. un pedido vencido)."""
    from usuarios.roles import obtener_rol

    if usuario is None:
        quien = "automáticamente por el sistema"
    else:
        quien = QUIEN_CANCELA.get(obtener_rol(usuario), "por el cliente")
    lineas = [f"El pedido {pedido.numero_pedido} fue cancelado {quien}."]
    if pedido.motivo_cancelacion:
        lineas.append(f"Motivo: {pedido.motivo_cancelacion}")
    notificar_evento_sede(
        pedido.sede_id, EventoSede.CANCELACION, f"Pedido {pedido.numero_pedido} cancelado", "\n".join(lineas)
    )


def avisar_sobrecupo(sede_id, estado):
    """`estado` es el dict de pedidos.capacidad.estado_capacidad."""
    notificar_evento_sede(
        sede_id,
        EventoSede.SOBRECUPO,
        "Capacidad casi llena",
        f"La sede tiene {estado['activos']} de {estado['maximo']} pedidos simultáneos en curso "
        f"(la alerta empieza en {estado['umbral_alerta']}).\n"
        "Considera pausar pedidos o reforzar la cocina.",
    )


# --- API del administrador ---------------------------------------------------------


class SuscripcionNotificacionSerializer(serializers.ModelSerializer):
    evento_nombre = serializers.CharField(source="get_evento_display", read_only=True)
    rol_nombre = serializers.CharField(source="get_rol_display", read_only=True)

    class Meta:
        model = SuscripcionNotificacion
        fields = ["id", "sede", "evento", "evento_nombre", "rol", "rol_nombre", "correo", "creada_en"]
        read_only_fields = ["creada_en"]
        # Las restricciones de la tabla se validan abajo con mensajes claros.
        validators = []

    def validate_correo(self, valor):
        return valor.strip().lower()

    def validate(self, datos):
        rol, correo = datos.get("rol", ""), datos.get("correo", "")
        if bool(rol) == bool(correo):
            raise serializers.ValidationError({"detail": "Indica un rol o un correo (solo uno de los dos)."})

        repetida = SuscripcionNotificacion.objects.filter(sede=datos["sede"], evento=datos["evento"])
        if rol and repetida.filter(rol=rol).exists():
            raise serializers.ValidationError({"rol": "Ese rol ya recibe este aviso en la sede."})
        if correo and repetida.filter(correo=correo).exists():
            raise serializers.ValidationError({"correo": "Ese correo ya recibe este aviso en la sede."})
        return datos


@extend_schema_view(
    list=extend_schema(
        summary="Suscripciones a los avisos de una sede",
        parameters=[OpenApiParameter("sede", int, description="Id de la sede (opcional).")],
    ),
    create=extend_schema(
        summary="Suscribir un rol o un correo a un evento de la sede",
        description="Envía `rol` o `correo`, no los dos. Eventos: stock_bajo, cancelacion, sobrecupo.",
        responses={201: SuscripcionNotificacionSerializer, 400: OpenApiResponse(description="Datos inválidos o repetidos.")},
    ),
    destroy=extend_schema(summary="Quitar una suscripción", responses={204: None}),
)
@extend_schema(tags=["Notificaciones de la sede"])
class SuscripcionNotificacionViewSet(
    mixins.ListModelMixin, mixins.CreateModelMixin, mixins.DestroyModelMixin, viewsets.GenericViewSet
):
    """HU-83: el administrador configura quién recibe los avisos de cada sede."""

    serializer_class = SuscripcionNotificacionSerializer

    def get_permissions(self):
        from .views import EsAdministradorPermission

        return [EsAdministradorPermission()]

    def get_queryset(self):
        queryset = SuscripcionNotificacion.objects.all()
        sede = self.request.query_params.get("sede")
        if sede:
            if not sede.isdigit():
                raise serializers.ValidationError({"sede": "Debe ser un número."})
            queryset = queryset.filter(sede_id=sede)
        return queryset
