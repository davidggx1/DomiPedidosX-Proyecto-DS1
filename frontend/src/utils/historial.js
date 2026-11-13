// HU-66 · Utilidades del historial de pedidos.

export const PEDIDOS_POR_PAGINA = 20

export function totalPaginas(total, porPagina = PEDIDOS_POR_PAGINA) {
  return Math.max(1, Math.ceil(total / porPagina))
}

// "Mostrando 21–25 de 25 pedidos"
export function textoRango(pagina, total, porPagina = PEDIDOS_POR_PAGINA) {
  if (total === 0) return 'Sin pedidos'
  const desde = (pagina - 1) * porPagina + 1
  const hasta = Math.min(pagina * porPagina, total)
  return `Mostrando ${desde}–${hasta} de ${total} ${total === 1 ? 'pedido' : 'pedidos'}`
}

// Quién hizo un cambio de estado: el correo del usuario o "Sistema" (asignación o vencimiento automático).
export function autorDelPaso(paso) {
  return paso.usuario || 'Sistema'
}
