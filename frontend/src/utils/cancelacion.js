// HU-34 · Motivos con los que el operador cancela un pedido.
// Se guardan como texto en el pedido ("Etiqueta: detalle"), así el cliente los
// lee tal cual en su correo y en el historial.

// Mismo máximo que el backend (pedidos/cancelacion.py)
export const MOTIVO_MAXIMO = 500
export const DETALLE_MINIMO = 5

export const MOTIVOS_CANCELACION = [
  { valor: 'cliente', etiqueta: 'El cliente lo solicitó' },
  { valor: 'agotado', etiqueta: 'Producto agotado' },
  { valor: 'direccion', etiqueta: 'Dirección errada o fuera de cobertura' },
  { valor: 'incidente', etiqueta: 'Incidente en la sede' },
  { valor: 'otro', etiqueta: 'Otro motivo' },
]

function etiquetaDe(codigo) {
  return MOTIVOS_CANCELACION.find((m) => m.valor === codigo)?.etiqueta ?? null
}

// Texto que viaja al backend: "Producto agotado: no hay pan" o solo el detalle si es "otro".
export function armarMotivo(codigo, detalle = '') {
  const limpio = detalle.trim().replace(/\s+/g, ' ')
  if (codigo === 'otro') return limpio
  const etiqueta = etiquetaDe(codigo) ?? ''
  return limpio ? `${etiqueta}: ${limpio}` : etiqueta
}

// Errores por campo, o {} si se puede enviar.
export function validarMotivo(codigo, detalle = '') {
  if (!etiquetaDe(codigo)) return { codigo: 'Elige el motivo de la cancelación.' }
  const limpio = detalle.trim()
  if (codigo === 'otro' && limpio.length < DETALLE_MINIMO) {
    return { detalle: `Describe el motivo (al menos ${DETALLE_MINIMO} caracteres).` }
  }
  if (armarMotivo(codigo, detalle).length > MOTIVO_MAXIMO) {
    return { detalle: `El motivo no puede superar ${MOTIVO_MAXIMO} caracteres.` }
  }
  return {}
}
