"""HU-64 · Cupo diario de usos de promociones y combos.

Un cupo es el máximo de usos por día de una oferta (`Promocion` o `ComboSede`).
No hay contador guardado: los usos de hoy se cuentan desde las filas de consumo por
su fecha, y los pedidos cancelados no cuentan. Por eso:

- el reinicio a las 00:00 es automático (mañana ya no hay filas con fecha de mañana), sin
  Celery Beat ni cron que pueda fallar o atrasarse;
- cancelar un pedido el mismo día devuelve la unidad sola; cancelar uno de ayer no toca
  el cupo de hoy.

La zona horaria es la de settings.TIME_ZONE (America/Bogota), igual que el resto del
sistema, porque se usa `timezone.localdate()` y el lookup `__date`.

Uso desde la confirmación del pedido (HU-65), dentro de la transacción:

    cupos.consumir(promocion, pedido)          # lanza CupoAgotado si ya no hay cupo
"""
from django.db.models import Sum
from django.utils import timezone

from .models import ComboSede, ConsumoCupoPromocion, Promocion


class CupoAgotado(Exception):
    """La oferta no tiene cupo para este uso. `mensaje` se le muestra al cliente."""

    def __init__(self, oferta, restante=0):
        self.oferta = oferta
        self.restante = restante
        nombre = _nombre(oferta)
        self.mensaje = f"«{nombre}» agotó su cupo de usos de hoy. Vuelve a intentarlo mañana."
        super().__init__(self.mensaje)


def _nombre(oferta):
    return oferta.combo.nombre if isinstance(oferta, ComboSede) else oferta.nombre


def usos_hoy(oferta, hoy=None):
    """Unidades usadas hoy, sin contar pedidos cancelados."""
    from pedidos.models import ConsumoCupoCombo, EstadoPedido

    hoy = hoy or timezone.localdate()
    if isinstance(oferta, ComboSede):
        consumos = ConsumoCupoCombo.objects.filter(combo_sede=oferta, fecha_consumo__date=hoy)
        return (
            consumos.exclude(pedido__estado=EstadoPedido.CANCELADO)
            .aggregate(total=Sum("cantidad_usada"))["total"]
            or 0
        )
    return (
        ConsumoCupoPromocion.objects.filter(promocion=oferta, fecha_consumo__date=hoy)
        .exclude(pedido__estado=EstadoPedido.CANCELADO)
        .count()
    )


def cupo_restante(oferta, hoy=None):
    """Usos que quedan hoy, o None si la oferta no tiene cupo."""
    if oferta.cupo_max_diario is None:
        return None
    return max(oferta.cupo_max_diario - usos_hoy(oferta, hoy), 0)


def consumir(oferta, pedido, cantidad=1):
    """Registra el uso de la oferta por `pedido`. Debe llamarse dentro de una transacción.

    Bloquea la fila de la oferta, así dos pedidos simultáneos no pueden pasarse del cupo:
    el segundo espera, recuenta y es rechazado si ya no queda.
    Lanza CupoAgotado si no alcanza. Devuelve el consumo creado.
    """
    modelo = type(oferta)
    oferta = modelo.objects.select_for_update().get(pk=oferta.pk)

    restante = cupo_restante(oferta)
    if restante is not None and cantidad > restante:
        raise CupoAgotado(oferta, restante)

    if isinstance(oferta, Promocion):
        return ConsumoCupoPromocion.objects.create(promocion=oferta, pedido=pedido)

    from pedidos.models import ConsumoCupoCombo

    return ConsumoCupoCombo.objects.create(
        combo_sede=oferta, pedido=pedido, cantidad_usada=cantidad
    )