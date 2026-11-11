"""Descuento de stock y bloqueo automático de agotados (HU-15) y reintegro al cancelar (HU-25)."""
from collections import defaultdict
from decimal import Decimal

from inventario.models import InventarioInsumo, InventarioProducto
from menu.models import Producto, ProductoInsumo
from promociones.models import ComboProducto


def descontar_stock(*, inv_producto, inv_insumo, cant_producto, cant_insumo):
    """Descuenta existencias y marca como no disponible lo que llega a 0.

    Recibe las filas de inventario YA bloqueadas (select_for_update) y validadas
    por _preparar_carrito, así que aquí el stock alcanza. Debe correr dentro de
    la transacción de confirmar_pedido.
    """
    for producto_id, cantidad in cant_producto.items():
        inv = inv_producto[producto_id]
        inv.stock_actual -= cantidad
        if inv.stock_actual <= 0:
            inv.disponible = False
        inv.save(update_fields=["stock_actual", "disponible", "fecha_actualizacion"])

    for insumo_id, cantidad in cant_insumo.items():
        inv = inv_insumo[insumo_id]
        inv.stock_actual -= cantidad
        if inv.stock_actual <= 0:
            inv.disponible = False
        inv.save(update_fields=["stock_actual", "disponible", "fecha_actualizacion"])


def cantidades_retenidas(pedido):
    """Lo que el pedido descontó al confirmarse: ({producto_id: n}, {insumo_id: n}).

    Sigue las reglas de _preparar_carrito: productos terminados por unidad,
    productos por insumos según su receta (sin los ingredientes excluidos) y
    combos según los productos que incluyen. Las adiciones no descuentan stock.
    """
    detalles = list(pedido.detalles.select_related("producto").prefetch_related("exclusiones"))

    # (producto, unidades, insumos excluidos) de cada línea, abriendo los combos.
    pedidos = []
    combo_ids = {d.combo_id for d in detalles if d.combo_id}
    incluidos = defaultdict(list)
    for cp in ComboProducto.objects.select_related("producto").filter(combo_id__in=combo_ids):
        incluidos[cp.combo_id].append(cp)
    for d in detalles:
        if d.producto_id:
            pedidos.append((d.producto, d.cantidad, {e.insumo_id for e in d.exclusiones.all()}))
        else:
            for cp in incluidos[d.combo_id]:
                pedidos.append((cp.producto, d.cantidad * cp.cantidad, set()))

    recetas = defaultdict(list)
    for pi in ProductoInsumo.objects.filter(producto_id__in={p.pk for p, _, _ in pedidos}):
        recetas[pi.producto_id].append(pi)

    cant_producto = defaultdict(int)
    cant_insumo = defaultdict(Decimal)
    for producto, unidades, excluidos in pedidos:
        if producto.tipo_control_stock == Producto.TipoControlStock.PRODUCTO:
            cant_producto[producto.pk] += unidades
        elif producto.tipo_control_stock == Producto.TipoControlStock.INSUMOS:
            for pi in recetas[producto.pk]:
                if pi.insumo_id not in excluidos:
                    cant_insumo[pi.insumo_id] += pi.cantidad_necesaria * unidades
    return dict(cant_producto), dict(cant_insumo)


def reintegrar_stock(pedido):
    """Devuelve a la sede el stock que retuvo el pedido (HU-25, criterio 3).

    Si una fila estaba agotada (en 0) y vuelve a tener existencias, se habilita
    de nuevo; si el operador la deshabilitó con stock, se respeta. Debe correr
    dentro de la transacción de la cancelación.
    """
    cant_producto, cant_insumo = cantidades_retenidas(pedido)
    filas = [
        (InventarioProducto, "producto_id", cant_producto),
        (InventarioInsumo, "insumo_id", cant_insumo),
    ]
    for modelo, campo, cantidades in filas:
        inventario = (
            modelo.objects.select_for_update()
            .filter(sede_id=pedido.sede_id, **{f"{campo}__in": list(cantidades)})
            .order_by("pk")
        )
        for inv in inventario:
            agotado = inv.stock_actual <= 0
            inv.stock_actual += cantidades[getattr(inv, campo)]
            if agotado and inv.stock_actual > 0:
                inv.disponible = True
            inv.save(update_fields=["stock_actual", "disponible", "fecha_actualizacion"])
