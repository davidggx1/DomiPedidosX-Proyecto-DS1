// Minutes between a date (ISO text) and a moment in milliseconds
export function minutosEntre(desde, hasta) {
  return Math.max(0, Math.floor((hasta - new Date(desde).getTime()) / 60000))
}

// 5 -> "5 min", 65 -> "1 h 5 min"
export function textoDuracion(minutos) {
  if (minutos < 60) return `${minutos} min`
  const resto = minutos % 60
  return resto === 0 ? `${Math.floor(minutos / 60)} h` : `${Math.floor(minutos / 60)} h ${resto} min`
}

export function horaCorta(fecha) {
  return new Date(fecha).toLocaleTimeString('es-CO', { hour: '2-digit', minute: '2-digit' })
}

// "12 nov 2026"
export function fechaCorta(fecha) {
  return new Date(fecha).toLocaleDateString('es-CO', { day: 'numeric', month: 'short', year: 'numeric' })
}

// "12 nov 2026, 07:14 p. m."
export function fechaHora(fecha) {
  return new Date(fecha).toLocaleString('es-CO', {
    day: 'numeric', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit',
  })
}
