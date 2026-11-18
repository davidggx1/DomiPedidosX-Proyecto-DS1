"""Cálculo dinámico del tiempo estimado de entrega (HU-48)."""
from collections import defaultdict

from menu.models import Producto
from promociones.models import ComboProducto

from .capacidad import ESTADOS_QUE_OCUPAN_CUPO, franja_actual
from .models import Pedido

MARGEN_RANGO_MINUTOS = 10
MINUTOS_POR_PEDIDO_EN_COLA = 3


def calcular_tiempo_preparacion(items) -> int:
    """Suma los minutos de preparación de todos los productos y combos del carrito."""
    if not items:
        return 0

    producto_ids = {i["producto_id"] for i in items if i.get("producto_id")}
    combo_ids = {i["combo_id"] for i in items if i.get("combo_id")}

    incluidos_por_combo = defaultdict(list)
    if combo_ids:
        for cp in ComboProducto.objects.filter(combo_id__in=combo_ids):
            incluidos_por_combo[cp.combo_id].append(cp)
            producto_ids.add(cp.producto_id)

    tiempos_producto = dict(
        Producto.objects.filter(pk__in=producto_ids).values_list("pk", "tiempo_preparacion")
    )

    total_prep = 0
    for item in items:
        cantidad = int(item.get("cantidad", 1))
        if item.get("producto_id"):
            total_prep += tiempos_producto.get(item["producto_id"], 0) * cantidad
        elif item.get("combo_id"):
            prep_combo = sum(
                tiempos_producto.get(cp.producto_id, 0) * cp.cantidad
                for cp in incluidos_por_combo.get(item["combo_id"], [])
            )
            total_prep += prep_combo * cantidad

    return total_prep


def calcular_congestion_cocina(sede) -> dict:
    """Calcula minutos extra por carga actual de cocina en la sede."""
    activos = Pedido.objects.filter(
        sede=sede, estado__in=ESTADOS_QUE_OCUPAN_CUPO
    ).count()

    franja = franja_actual(sede)
    maximo = franja.max_pedidos_simultaneos if franja else None
    umbral = franja.umbral_alerta if franja else None

    minutos_cola = activos * MINUTOS_POR_PEDIDO_EN_COLA
    recargo_saturacion = 0
    nivel = "normal"

    if activos > 0:
        if umbral is not None and activos >= umbral:
            recargo_saturacion = 8
            nivel = "alta"
        elif maximo and (activos / maximo) >= 0.5:
            recargo_saturacion = 4
            nivel = "moderada"

    return {
        "pedidos_activos": activos,
        "minutos": minutos_cola + recargo_saturacion,
        "nivel": nivel,
    }


def estimar_tiempo_entrega(*, sede, zona, items) -> dict:
    """Combina preparación + congestión de cocina + tiempo base de zona."""
    prep_min = calcular_tiempo_preparacion(items)
    congestion = calcular_congestion_cocina(sede)
    zona_min = int(zona.tiempo_estimado or 0)

    tiempo_min = prep_min + congestion["minutos"] + zona_min
    tiempo_max = tiempo_min + MARGEN_RANGO_MINUTOS

    return {
        "tiempo_estimado_min": tiempo_min,
        "tiempo_estimado_max": tiempo_max,
        "tiempo_estimado_rango": f"{tiempo_min}-{tiempo_max} min",
        "desglose": {
            "preparacion_min": prep_min,
            "congestion_min": congestion["minutos"],
            "zona_min": zona_min,
            "pedidos_activos_cocina": congestion["pedidos_activos"],
            "nivel_carga_cocina": congestion["nivel"],
        },
    }


def rango_desde_pedido(pedido) -> dict | None:
    """Devuelve el rango estimado guardado al confirmar un pedido."""
    if pedido.tiempo_estimado_entrega is None:
        return None
    tmin = pedido.tiempo_estimado_entrega
    tmax = tmin + MARGEN_RANGO_MINUTOS
    return {
        "tiempo_estimado_min": tmin,
        "tiempo_estimado_max": tmax,
        "tiempo_estimado_rango": f"{tmin}-{tmax} min",
    }