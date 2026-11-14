"""
Rango de fechas de los reportes (HU-72; pensado para reutilizarlo en la HU-71).

    from pedidos.rango_fechas import leer_rango_fechas, RangoFechasInvalido

    try:
        desde, hasta, inicio, fin = leer_rango_fechas(request.query_params)
    except RangoFechasInvalido as error:
        return Response(error.errores, status=400)

- `?desde=AAAA-MM-DD&hasta=AAAA-MM-DD`, los dos días incluidos, en hora local.
- Sin fechas: los últimos 7 días contando hoy.
- Rechaza fechas mal escritas, inicio posterior al fin y rangos de más de un año.
- `inicio` y `fin` son datetimes con zona horaria para filtrar: `__gte=inicio, __lt=fin`.
"""
from datetime import date, timedelta

from django.utils import timezone

from .resumen import rango_del_dia

DIAS_POR_DEFECTO = 7
MAXIMO_DIAS = 366


class RangoFechasInvalido(Exception):
    def __init__(self, errores):
        super().__init__(errores)
        self.errores = errores


def _leer_fecha(texto, campo):
    try:
        return date.fromisoformat(texto)
    except ValueError:
        raise RangoFechasInvalido({campo: "Usa el formato AAAA-MM-DD, por ejemplo 2026-11-13."}) from None


def leer_rango_fechas(parametros, hoy=None):
    hoy = hoy or timezone.localdate()
    texto_desde, texto_hasta = parametros.get("desde"), parametros.get("hasta")
    hasta = _leer_fecha(texto_hasta, "hasta") if texto_hasta else hoy
    desde = _leer_fecha(texto_desde, "desde") if texto_desde else hasta - timedelta(days=DIAS_POR_DEFECTO - 1)

    if desde > hasta:
        raise RangoFechasInvalido({"desde": "La fecha de inicio no puede ser posterior a la fecha de fin."})
    if (hasta - desde).days + 1 > MAXIMO_DIAS:
        raise RangoFechasInvalido({"desde": "El rango no puede ser de más de un año."})

    inicio, _ = rango_del_dia(desde)
    _, fin = rango_del_dia(hasta)
    return desde, hasta, inicio, fin
