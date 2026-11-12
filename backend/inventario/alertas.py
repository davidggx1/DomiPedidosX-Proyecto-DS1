"""
Low stock alerts (HU-16)

After every save of an InventarioProducto or InventarioInsumo the alert of that
item is brought up to date. The stock changes through descontar_stock,
reintegrar_stock and the operator's own edits, and all of them end in a save,
so one receiver covers every path

- stock <= stock_minimo and no active alert -> a new one is created ("creada")
- stock <= stock_minimo and one is active -> nothing is created again, the
  operators only get the new numbers ("actualizada")
- stock > stock_minimo and one is active -> it is marked as resolved ("resuelta")

Changing the minimum is also a save, so it re-evaluates the alert. A product
only has its own stock when its tipo_control_stock is PRODUCTO, the others do
not alert. A minimum of 0 alerts when the item runs out

The event goes to the operators of the sede (group pedidos_sede_<id>), through
the same socket of the panel, and never breaks the save that caused it
"""
import logging
from decimal import Decimal

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.db import IntegrityError, transaction
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver
from django.utils import timezone

from menu.models import Producto

from .models import AlertaInventario, InventarioInsumo, InventarioProducto

logger = logging.getLogger(__name__)

TIPO_EVENTO = "alerta_inventario"
CREADA = "creada"
ACTUALIZADA = "actualizada"
RESUELTA = "resuelta"

CAMPOS_DE_STOCK = {"stock_actual", "stock_minimo"}


def _numero(valor):
    """JSON number: whole values as int, the rest as float."""
    if isinstance(valor, Decimal):
        return int(valor) if valor == valor.to_integral_value() else float(valor)
    return valor


def datos_alerta(alerta, inventario=None):
    """Alert as a dict for the API and the WebSocket event."""
    if inventario is None:
        modelo, campo = (
            (InventarioProducto, "producto_id")
            if alerta.producto_id
            else (InventarioInsumo, "insumo_id")
        )
        inventario = modelo.objects.filter(
            sede_id=alerta.sede_id, **{campo: getattr(alerta, campo)}
        ).first()

    if alerta.producto_id:
        item, tipo, unidad = alerta.producto, "producto", "unidad"
    else:
        item, tipo, unidad = alerta.insumo, "insumo", alerta.insumo.unidad_medida

    return {
        "id": alerta.pk,
        "tipo": tipo,
        "item_id": item.pk,
        "nombre": item.nombre,
        "unidad": unidad,
        "sede": alerta.sede_id,
        "estado": alerta.estado,
        "stock_actual": _numero(inventario.stock_actual) if inventario else None,
        "stock_minimo": _numero(inventario.stock_minimo) if inventario else None,
        "stock_al_disparar": _numero(alerta.stock_al_disparar),
        "creada_en": alerta.creada_en.isoformat(),
        "resuelta_en": alerta.resuelta_en.isoformat() if alerta.resuelta_en else None,
    }


def _avisar(alerta, inventario, transicion):
    """Sends the event to the operators of the sede once the transaction commits."""
    sede_id = alerta.sede_id
    evento = {
        "type": "pedido.evento",
        "data": {
            "tipo": TIPO_EVENTO,
            "transicion": transicion,
            "alerta": datos_alerta(alerta, inventario),
        },
    }

    def enviar():
        try:
            # imported here: pedidos depends on inventario, not the other way
            from pedidos.consumers import grupo_sede

            async_to_sync(get_channel_layer().group_send)(grupo_sede(sede_id), evento)
        except Exception:
            logger.exception("No se pudo enviar la alerta de inventario %s", alerta.pk)

    transaction.on_commit(enviar)


def _resolver(alerta, inventario):
    alerta.estado = AlertaInventario.Estado.RESUELTA
    alerta.resuelta_en = timezone.now()
    alerta.save(update_fields=["estado", "resuelta_en"])
    _avisar(alerta, inventario, RESUELTA)


def _sincronizar(inventario, campo_item, item, aplica):
    """Brings the alert of this item up to date with its stock."""
    filtro = {
        "sede_id": inventario.sede_id,
        f"{campo_item}_id": item.pk,
        "estado": AlertaInventario.Estado.ACTIVA,
    }
    activa = AlertaInventario.objects.filter(**filtro).first()
    bajo = aplica and inventario.stock_actual <= inventario.stock_minimo

    if bajo and activa is None:
        try:
            with transaction.atomic():
                activa = AlertaInventario.objects.create(
                    sede_id=inventario.sede_id,
                    **{campo_item: item},
                    stock_al_disparar=inventario.stock_actual,
                    stock_minimo_al_disparar=inventario.stock_minimo,
                )
            transicion = CREADA
        except IntegrityError:
            # another save created it at the same moment, this one only updates
            activa = AlertaInventario.objects.get(**filtro)
            transicion = ACTUALIZADA
        _avisar(activa, inventario, transicion)
    elif bajo:
        _avisar(activa, inventario, ACTUALIZADA)
    elif activa is not None:
        _resolver(activa, inventario)


def _toca_el_stock(kwargs):
    campos = kwargs.get("update_fields")
    return campos is None or bool(CAMPOS_DE_STOCK & set(campos))


@receiver(post_save, sender=InventarioProducto)
def alertar_stock_de_producto(sender, instance, **kwargs):
    if not _toca_el_stock(kwargs):
        return
    producto = instance.producto
    aplica = producto.tipo_control_stock == Producto.TipoControlStock.PRODUCTO
    _sincronizar(instance, "producto", producto, aplica)


@receiver(post_save, sender=InventarioInsumo)
def alertar_stock_de_insumo(sender, instance, **kwargs):
    if not _toca_el_stock(kwargs):
        return
    insumo = instance.insumo
    _sincronizar(instance, "insumo", insumo, insumo.activo)


def _resolver_al_quitar(inventario, campo_item):
    """The item is no longer stocked in the sede: its active alert is closed."""
    activa = AlertaInventario.objects.filter(
        sede_id=inventario.sede_id,
        estado=AlertaInventario.Estado.ACTIVA,
        **{f"{campo_item}_id": getattr(inventario, f"{campo_item}_id")},
    ).first()
    if activa is not None:
        _resolver(activa, inventario)


@receiver(post_delete, sender=InventarioProducto)
def cerrar_alerta_al_quitar_producto(sender, instance, **kwargs):
    _resolver_al_quitar(instance, "producto")


@receiver(post_delete, sender=InventarioInsumo)
def cerrar_alerta_al_quitar_insumo(sender, instance, **kwargs):
    _resolver_al_quitar(instance, "insumo")
