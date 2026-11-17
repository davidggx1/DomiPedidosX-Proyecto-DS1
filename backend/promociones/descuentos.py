import re
from decimal import ROUND_HALF_UP, Decimal

from django.utils import timezone
from rest_framework.exceptions import ValidationError

from . import cupos
from .models import EstadoPromocion, Promocion, TipoDescuento

CENTAVOS = Decimal("0.01")
CERO = Decimal("0.00")


def _redondear(valor: Decimal) -> Decimal:
    return valor.quantize(CENTAVOS, rounding=ROUND_HALF_UP)


def _extraer_monto_minimo(condiciones: str) -> Decimal | None:
    if not condiciones:
        return None
    match = re.search(
        r"(?:m[ií]nim[oa]|desde|mayor\s+a|superior\s+a)\s*(?:de\s*)?\$?\s*([\d.,]+)",
        condiciones,
        flags=re.IGNORECASE,
    )
    if not match:
        return None
    bruto = match.group(1).strip()
    if re.fullmatch(r"\d{1,3}(?:\.\d{3})+", bruto):
        limpio = bruto.replace(".", "")
    else:
        limpio = bruto.replace(",", "")
    try:
        valor = Decimal(limpio)
        return valor if valor > CERO else None
    except Exception:
        return None


def validar_y_calcular_descuento(
    *,
    sede,
    subtotal: Decimal,
    codigo_promocion: str | None = None,
    promocion_id: int | None = None,
):
    """
    Valida una promoción para la `sede` y el `subtotal` dados y calcula el descuento.
    Reutiliza `promociones.cupos` para verificar la bolsa diaria (Criterio 3).
    """
    codigo = (codigo_promocion or "").strip()
    if not codigo and not promocion_id:
        return None, CERO

    if subtotal <= CERO:
        raise ValidationError(
            {"codigo_promocion": ["Agrega productos al carrito antes de aplicar un cupón."]}
        )

    qs = Promocion.objects.filter(sede=sede)
    if promocion_id is not None:
        promocion = qs.filter(pk=promocion_id).first()
    else:
        promocion = qs.filter(nombre__iexact=codigo).order_by("-activa", "-id").first()

    if promocion is None:
        raise ValidationError(
            {"codigo_promocion": ["El cupón ingresado no existe o no aplica para esta sede."]}
        )

    # Criterio 2: Rechazar cupones inactivos, programados o vencidos informando la causa
    hoy = timezone.localdate()
    estado = promocion.estado(hoy)
    if estado == EstadoPromocion.INACTIVA:
        raise ValidationError(
            {"codigo_promocion": [f'El cupón "{promocion.nombre}" ya no se encuentra activo.']}
        )
    if estado == EstadoPromocion.PROGRAMADA:
        raise ValidationError(
            {
                "codigo_promocion": [
                    f'El cupón "{promocion.nombre}" aún no está vigente '
                    f"(inicia el {promocion.fecha_inicio:%d/%m/%Y})."
                ]
            }
        )
    if estado == EstadoPromocion.VENCIDA:
        raise ValidationError(
            {
                "codigo_promocion": [
                    f'El cupón "{promocion.nombre}" venció el {promocion.fecha_fin:%d/%m/%Y}.'
                ]
            }
        )

    # Criterio 2: Validar compra mínima si está definida en `condiciones`
    monto_minimo = _extraer_monto_minimo(promocion.condiciones)
    if monto_minimo is not None and subtotal < monto_minimo:
        faltante = monto_minimo - subtotal
        raise ValidationError(
            {
                "codigo_promocion": [
                    f'El cupón "{promocion.nombre}" requiere una compra mínima de '
                    f"${monto_minimo:,.0f} (te faltan ${faltante:,.0f})."
                ]
            }
        )

    # Criterio 3: Verificar bolsa diaria usando `promociones/cupos.py`
    restante = cupos.cupo_restante(promocion, hoy)
    if restante is not None and restante <= 0:
        raise ValidationError({"codigo_promocion": [cupos.CupoAgotado(promocion, 0).mensaje]})

    # Criterio 1: Calcular descuento (porcentaje o valor fijo, topado al subtotal)
    if promocion.tipo_descuento == TipoDescuento.PORCENTAJE:
        descuento = _redondear(subtotal * (promocion.valor / Decimal("100")))
    else:
        descuento = _redondear(promocion.valor)

    if descuento > subtotal:
        descuento = subtotal

    return promocion, descuento