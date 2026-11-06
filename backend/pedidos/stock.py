"""Descuento de stock y bloqueo automático de agotados (HU-15)."""


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