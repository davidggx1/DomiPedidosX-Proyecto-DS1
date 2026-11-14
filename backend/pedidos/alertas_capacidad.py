"""
Capacity alerts for the operator (HU-60)

Every time the number of orders that use a slot of the sede changes (see
capacidad.ESTADOS_QUE_OCUPAN_CUPO), the operators of that sede get a WebSocket
event "capacidad_actualizada" with the current state, so the panel can show
"16 de 20 pedidos ocupados" in real time.

The event also carries `transicion`:
- "alerta_activada": the sede just reached the umbral_alerta of its slot
- "alerta_desactivada": it just went back under it
- None: any other change. While the sede stays over the umbral nothing is
  repeated, and the panel keeps ONE banner that always follows the last state

A sede without a slot for the current day and hour sends no order events (there
is no limit to compare). The panel learns it when the admin changes the slots,
when it reconnects, and in its request every minute

Only the operators of the sede receive it (the group is pedidos_sede_<id>).
When the alert turns on, the people subscribed to "sobrecupo" in that sede also
get a mail (HU-83, sedes/notificaciones.py)
"""
import logging

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.db import transaction
from django.db.models.signals import post_delete, post_save, pre_save
from django.dispatch import receiver

from sedes.models import CapacidadSede, Sede
from sedes.notificaciones import avisar_sobrecupo

from . import capacidad
from .consumers import grupo_sede
from .models import Pedido

logger = logging.getLogger(__name__)

TIPO_EVENTO = "capacidad_actualizada"
ALERTA_ACTIVADA = "alerta_activada"
ALERTA_DESACTIVADA = "alerta_desactivada"


def _ocupa_cupo(estado):
    return estado in capacidad.ESTADOS_QUE_OCUPAN_CUPO


def transicion_de_alerta(activos, umbral, cambio):
    """
    Did the alert turn on or off with this change?
    `cambio` is +1 if an order started using a slot and -1 if it stopped
    """
    antes = activos - cambio
    if cambio > 0 and antes < umbral <= activos:
        return ALERTA_ACTIVADA
    if cambio < 0 and activos < umbral <= antes:
        return ALERTA_DESACTIVADA
    return None


def emitir_estado_capacidad(sede_id, cambio=0):
    """
    Sends the current capacity of the sede to its operators. A failure of the
    channel never breaks the order or the change that caused it
    """
    try:
        sede = Sede.objects.get(pk=sede_id)
        estado = capacidad.estado_capacidad(sede, puede_confirmar_manual=True)

        # Without a slot an order changes nothing the panel can show. Only a
        # change of the slots themselves (cambio == 0) is worth telling
        if cambio and estado["estado"] == capacidad.SIN_FRANJA:
            return

        transicion = None
        if cambio and estado["maximo"] is not None:
            transicion = transicion_de_alerta(
                estado["activos"], estado["umbral_alerta"], cambio
            )

        evento = {
            "type": "pedido.evento",
            "data": {"tipo": TIPO_EVENTO, "transicion": transicion, "capacidad": estado},
        }
        async_to_sync(get_channel_layer().group_send)(grupo_sede(sede_id), evento)
    except Exception:
        logger.exception("No se pudo avisar la capacidad de la sede %s", sede_id)
        return

    # HU-83: the subscribers of the sede get a mail, only when the alert turns
    # on (not on every order while it stays over the umbral)
    if transicion == ALERTA_ACTIVADA:
        avisar_sobrecupo(sede_id, estado)


@receiver(pre_save, sender=Pedido)
def recordar_si_ocupaba_cupo(sender, instance, **kwargs):
    """Before saving: did the order use a slot? None if the state cannot change."""
    campos = kwargs.get("update_fields")
    if campos is not None and "estado" not in campos:
        instance._ocupaba_cupo = None
    elif instance._state.adding:
        instance._ocupaba_cupo = False
    else:
        estado = Pedido.objects.filter(pk=instance.pk).values_list("estado", flat=True).first()
        instance._ocupaba_cupo = _ocupa_cupo(estado)


@receiver(post_save, sender=Pedido)
def avisar_cambio_de_ocupacion(sender, instance, **kwargs):
    """After saving: if the order started or stopped using a slot, tell the operators."""
    antes = getattr(instance, "_ocupaba_cupo", None)
    if antes is None:
        return
    ahora = _ocupa_cupo(instance.estado)
    if antes == ahora:
        return

    sede_id = instance.sede_id
    cambio = 1 if ahora else -1
    # after the commit, so the count already includes this order
    transaction.on_commit(lambda: emitir_estado_capacidad(sede_id, cambio))


@receiver(post_save, sender=CapacidadSede)
@receiver(post_delete, sender=CapacidadSede)
def avisar_cambio_de_franja(sender, instance, **kwargs):
    """The admin changed a slot (limit, umbral or hours): the panel shows the new numbers."""
    sede_id = instance.sede_id
    transaction.on_commit(lambda: emitir_estado_capacidad(sede_id))
