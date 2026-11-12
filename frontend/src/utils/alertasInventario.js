// HU-16: low stock alerts. Pure helpers for the panel and the popup of the operator

export const TIPO_EVENTO_ALERTA = 'alerta_inventario'
export const DURACION_AVISO_MS = 12000

// The alert inside a WebSocket message, or null for any other message
export function alertaDeEvento(datos) {
  if (datos?.tipo !== TIPO_EVENTO_ALERTA || !datos.alerta) return null
  return { transicion: datos.transicion, alerta: datos.alerta }
}

// New list of active alerts after an event. One alert per item, so a second
// event about the same alert replaces it and never adds a duplicate
export function aplicarEvento(lista, evento) {
  const { transicion, alerta } = evento
  const sinEsta = lista.filter((actual) => actual.id !== alerta.id)
  if (transicion === 'resuelta' || alerta.estado === 'resuelta') return sinEsta
  return [alerta, ...sinEsta].sort((a, b) => b.creada_en.localeCompare(a.creada_en))
}

// 2,5 kg · 1 unidad · 3 unidades (the comma is the decimal mark)
function cantidad(valor, unidad) {
  const numero = String(valor).replace('.', ',')
  if (unidad === 'unidad') return `${numero} ${valor === 1 ? 'unidad' : 'unidades'}`
  return `${numero} ${unidad}`
}

// "Quedan 3 unidades (mínimo 5)", "Quedan 2,5 kg (mínimo 3 kg)" or "Agotado (mínimo 5)"
export function textoStock(alerta) {
  // units are not repeated in the minimum: "mínimo 5", not "mínimo 5 unidades"
  const minimo =
    alerta.unidad === 'unidad'
      ? String(alerta.stock_minimo).replace('.', ',')
      : cantidad(alerta.stock_minimo, alerta.unidad)
  if (alerta.stock_actual === 0) return `Agotado (mínimo ${minimo})`
  return `Quedan ${cantidad(alerta.stock_actual, alerta.unidad)} (mínimo ${minimo})`
}

// Popup for a NEW alert. Updates and resolutions do not pop up again
export function avisoDeEvento(evento) {
  if (evento.transicion !== 'creada') return null
  const { alerta } = evento
  return {
    id: `inventario-${alerta.id}`,
    titulo: `${alerta.stock_actual === 0 ? 'Agotado' : 'Stock bajo'}: ${alerta.nombre}`,
    texto: textoStock(alerta),
    enlace: '/operador/inventario',
  }
}
