// HU-57 · Pedido mínimo por zona. Solo cuenta el subtotal de productos (sin domicilio).

// Cuánto falta para llegar al mínimo. 0 si no hay mínimo, no se conoce o ya se alcanzó.
export function faltanteMinimo(subtotal, pedidoMinimo) {
  const minimo = Number(pedidoMinimo ?? 0)
  if (!Number.isFinite(minimo) || minimo <= 0) return 0
  return Math.max(minimo - Number(subtotal ?? 0), 0)
}