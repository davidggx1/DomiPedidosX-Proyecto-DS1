"""
Máquina de estados del pedido (HU-31).

Es la única puerta para cambiar `Pedido.estado`. La usan cocina (HU-31),
el operador (HU-28 aprobar, HU-34 cancelar), el repartidor (HU-45) y el
cliente (HU-25 cancelar). Así todas las historias comparten las mismas reglas:

- Solo se permiten los pasos de la tabla TRANSICIONES: no se saltan pasos
  ni se retrocede (HU-31, criterio 3).
- Cada paso lo puede dar solo el rol indicado.
- Cada cambio queda en HistorialEstadoPedido con fecha, hora y usuario
  (HU-31, criterio 4; HU-28, criterio 3).
- Después de guardar se envía la señal `estado_pedido_cambiado`, para que el
  tiempo real (WebSockets) avise al operador, a cocina y al cliente.

Flujo normal:
  pendiente_aprobacion → recibido → en_preparacion → listo_despacho
  → recogido → en_camino → entregado
Y "cancelado" desde cualquier estado anterior a "entregado", según el rol.
"""
from django.db import transaction
from django.dispatch import Signal

from usuarios.roles import ADMINISTRADOR, COCINA, OPERADOR, REPARTIDOR

from .models import EstadoPedido, HistorialEstadoPedido, Pedido

CLIENTE = "cliente"  # El cliente no es un rol de personal; se identifica por su perfil.

E = EstadoPedido

# (estado actual, estado nuevo): roles que pueden dar ese paso.
TRANSICIONES = {
    (E.PENDIENTE_APROBACION, E.RECIBIDO): {OPERADOR, ADMINISTRADOR},  # HU-28
    (E.RECIBIDO, E.EN_PREPARACION): {COCINA},  # HU-31
    (E.EN_PREPARACION, E.LISTO_DESPACHO): {COCINA},  # HU-31
    (E.LISTO_DESPACHO, E.RECOGIDO): {REPARTIDOR},  # HU-45
    (E.RECOGIDO, E.EN_CAMINO): {REPARTIDOR},  # HU-45
    (E.EN_CAMINO, E.ENTREGADO): {REPARTIDOR},  # HU-45
    # Cancelaciones
    (E.PENDIENTE_APROBACION, E.CANCELADO): {CLIENTE, OPERADOR, ADMINISTRADOR},  # HU-25, HU-34
    (E.RECIBIDO, E.CANCELADO): {CLIENTE, OPERADOR, ADMINISTRADOR, COCINA},  # HU-25, HU-33, HU-34
    (E.EN_PREPARACION, E.CANCELADO): {OPERADOR, ADMINISTRADOR, COCINA},  # HU-33, HU-34
    (E.LISTO_DESPACHO, E.CANCELADO): {OPERADOR, ADMINISTRADOR},  # HU-34
    (E.RECOGIDO, E.CANCELADO): {OPERADOR, ADMINISTRADOR},  # HU-34
    (E.EN_CAMINO, E.CANCELADO): {OPERADOR, ADMINISTRADOR},  # HU-34
}

# Estados en los que el pedido ya no cambia más.
ESTADOS_FINALES = {E.ENTREGADO, E.CANCELADO}

# Roles que deben escribir el motivo al cancelar (HU-33, HU-34).
CANCELAN_CON_MOTIVO = {OPERADOR, ADMINISTRADOR, COCINA}

# Se envía después de guardar el cambio. Argumentos: pedido, estado_anterior, usuario.
estado_pedido_cambiado = Signal()


class TransicionInvalida(Exception):
    """El cambio de estado no está permitido. `mensaje` se puede mostrar al usuario."""

    def __init__(self, mensaje, codigo="transicion_invalida"):
        super().__init__(mensaje)
        self.mensaje = mensaje
        self.codigo = codigo


def siguientes_estados(estado_actual, rol):
    """Estados a los que `rol` puede llevar un pedido que está en `estado_actual`."""
    return [
        nuevo
        for (actual, nuevo), roles in TRANSICIONES.items()
        if actual == estado_actual and rol in roles
    ]


def validar_transicion(estado_actual, estado_nuevo, rol, motivo=""):
    """Lanza TransicionInvalida si el paso no está permitido. No guarda nada."""
    if estado_nuevo not in E.values:
        raise TransicionInvalida("El estado indicado no existe.", "estado_desconocido")
    if estado_actual in ESTADOS_FINALES:
        etiqueta = E(estado_actual).label.lower()
        raise TransicionInvalida(f"El pedido ya está {etiqueta} y no se puede modificar.", "pedido_cerrado")
    if estado_nuevo == estado_actual:
        raise TransicionInvalida("El pedido ya está en ese estado.", "mismo_estado")

    roles = TRANSICIONES.get((estado_actual, estado_nuevo))
    if roles is None:
        raise TransicionInvalida(
            f'No se puede pasar de "{E(estado_actual).label}" a "{E(estado_nuevo).label}": '
            "no se pueden saltar pasos ni retroceder.",
            "paso_no_permitido",
        )
    if rol not in roles:
        raise TransicionInvalida(
            f'Tu rol no puede pasar el pedido a "{E(estado_nuevo).label}".', "rol_no_autorizado"
        )
    if estado_nuevo == E.CANCELADO and rol in CANCELAN_CON_MOTIVO and not motivo.strip():
        raise TransicionInvalida("Escribe el motivo de la cancelación.", "motivo_obligatorio")


def registrar_estado_inicial(pedido, usuario=None):
    """
    Guarda en el historial el estado con el que se creó el pedido.
    HU-23 y HU-24 deben llamarla justo después de crear el pedido.
    """
    return HistorialEstadoPedido.objects.create(pedido=pedido, usuario=usuario, estado=pedido.estado)


def cambiar_estado(pedido, estado_nuevo, usuario, rol, motivo=""):
    """
    Cambia el estado del pedido aplicando las reglas y lo registra en el historial.

    `rol` es el de quien hace el cambio (usuarios.roles o "cliente").
    Bloquea la fila mientras cambia, para que dos personas no muevan el mismo
    pedido a la vez. Devuelve el pedido actualizado.
    """
    with transaction.atomic():
        pedido = Pedido.objects.select_for_update().get(pk=pedido.pk)
        estado_anterior = pedido.estado
        validar_transicion(estado_anterior, estado_nuevo, rol, motivo)

        pedido.estado = estado_nuevo
        campos = ["estado"]
        if estado_nuevo == E.CANCELADO:
            pedido.motivo_cancelacion = motivo.strip()
            campos.append("motivo_cancelacion")
        pedido.save(update_fields=campos)

        HistorialEstadoPedido.objects.create(
            pedido=pedido, usuario=usuario, estado=estado_nuevo, observacion=motivo.strip()
        )

        transaction.on_commit(
            lambda: estado_pedido_cambiado.send(
                sender=Pedido, pedido=pedido, estado_anterior=estado_anterior, usuario=usuario
            )
        )
    return pedido
