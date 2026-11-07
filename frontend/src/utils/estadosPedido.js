// Name and badge colors of every order state (the same states as pedidos/models.py).
// The classes are written in full so Tailwind finds them when it builds the CSS.
export const ESTADOS_PEDIDO = {
  pendiente_aprobacion: { etiqueta: 'Pendiente de aprobación', clases: 'border-aviso text-aviso' },
  recibido: { etiqueta: 'Recibido', clases: 'border-borde text-texto-suave' },
  en_preparacion: { etiqueta: 'En preparación', clases: 'border-borde text-texto-suave' },
  listo_despacho: { etiqueta: 'Listo para despacho', clases: 'border-texto text-texto' },
  recogido: { etiqueta: 'Recogido', clases: 'border-texto text-texto' },
  en_camino: { etiqueta: 'En camino', clases: 'border-texto text-texto' },
  entregado: { etiqueta: 'Entregado', clases: 'border-exito text-exito' },
  cancelado: { etiqueta: 'Cancelado', clases: 'border-error text-error' },
}

// Unknown states still get a readable badge instead of breaking the page
export function datosEstado(estado) {
  return ESTADOS_PEDIDO[estado] ?? { etiqueta: estado, clases: 'border-borde text-texto-suave' }
}

// Phases of the flow, to group the counters of the daily summary (HU-67)
export const FASES_PEDIDO = [
  { titulo: 'Por aprobar', estados: ['pendiente_aprobacion'] },
  { titulo: 'En cocina', estados: ['recibido', 'en_preparacion', 'listo_despacho'] },
  { titulo: 'En entrega', estados: ['recogido', 'en_camino'] },
  { titulo: 'Cerrados', estados: ['entregado', 'cancelado'] },
]

// Orders still moving (neither delivered nor cancelled)
export function pedidosActivos(porEstado) {
  return Object.entries(porEstado)
    .filter(([estado]) => estado !== 'entregado' && estado !== 'cancelado')
    .reduce((total, [, cantidad]) => total + cantidad, 0)
}
