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
