"""HU-85 · Reglas de los combos: precio frente a la suma de sus productos y disponibilidad.

La disponibilidad no se guarda: se calcula al consultar, así el combo pasa a
"No disponible" apenas uno de sus productos se desactiva o se agota, y vuelve solo
cuando se repone.
"""
from decimal import Decimal

from django.utils import timezone

CERO = Decimal("0")


def suma_individual(lineas):
    """Suma de precio_base × cantidad. `lineas` = [(producto, cantidad)]."""
    return sum((producto.precio_base * cantidad for producto, cantidad in lineas), CERO)


def motivo_producto_no_disponible(producto, cantidad, sede):
    """Texto con el motivo si el producto no se puede servir en la sede; None si está bien."""
    from inventario.models import InventarioInsumo, InventarioProducto
    from menu.models import Producto, ProductoInsumo

    if not producto.activo or not producto.categoria.activa:
        return f"«{producto.nombre}» está desactivado."

    # Disponibilidad por sede: si el operador lo marcó como no disponible, cuenta para
    # cualquier tipo de control de stock.
    inv = InventarioProducto.objects.filter(sede=sede, producto=producto).first()
    if inv is not None and not inv.disponible:
        return f"«{producto.nombre}» no está disponible en esta sede."

    control = producto.tipo_control_stock
    if control == Producto.TipoControlStock.PRODUCTO:
        if inv is None or inv.stock_actual < cantidad:
            return f"«{producto.nombre}» está agotado."
    elif control == Producto.TipoControlStock.NINGUNO:
        # Sin control de receta: si la sede lleva su existencia en Inventario, se respeta.
        if inv is not None and inv.stock_actual < cantidad:
            return f"«{producto.nombre}» está agotado."
    elif control == Producto.TipoControlStock.INSUMOS:
        for receta in ProductoInsumo.objects.filter(producto=producto):
            inv_insumo = InventarioInsumo.objects.filter(sede=sede, insumo_id=receta.insumo_id).first()
            if (
                inv_insumo is None
                or not inv_insumo.disponible
                or inv_insumo.stock_actual < receta.cantidad_necesaria * cantidad
            ):
                return f"«{producto.nombre}» está agotado."
    return None


def detalle_productos(combo, sede):
    """[{producto, nombre, cantidad, precio_base, disponible, motivo}] de un combo en una sede."""
    resultado = []
    for item in combo.productos_incluidos.select_related("producto__categoria").order_by("id"):
        motivo = motivo_producto_no_disponible(item.producto, item.cantidad, sede)
        resultado.append({
            "producto": item.producto_id,
            "nombre": item.producto.nombre,
            "cantidad": item.cantidad,
            "precio_base": item.producto.precio_base,
            "disponible": motivo is None,
            "motivo": motivo,
        })
    return resultado


def disponibilidad(combo, combo_sede, detalle, hoy=None):
    """(disponible, motivo). Si algún producto falla, el combo entero no está disponible."""
    hoy = hoy or timezone.localdate()
    if not combo.activo or not combo_sede.activo:
        return False, "El combo está desactivado."
    if hoy < combo.fecha_inicio:
        return False, "El combo todavía no está vigente."
    if hoy > combo.fecha_vencimiento:
        return False, "El combo está vencido."
    for linea in detalle:
        if not linea["disponible"]:
            return False, linea["motivo"]
    return True, None