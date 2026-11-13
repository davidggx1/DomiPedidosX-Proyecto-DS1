// HU-70 · Utilidades del panel de indicadores del día.

// Cada cuánto se actualiza solo el panel.
export const INTERVALO_INDICADORES_MS = 60000

// Tiempo promedio de entrega en texto. Sin entregas todavía el valor es 0,
// pero se aclara para que no parezca que entregan en cero minutos.
export function textoTiempoEntrega(minutos, entregados) {
  if (!entregados) return { valor: '0 min', detalle: 'Aún no hay entregas hoy' }
  return {
    valor: `${minutos} min`,
    detalle: `Promedio de ${entregados} ${entregados === 1 ? 'entrega' : 'entregas'}`,
  }
}

// Nivel de ocupación de la cocina, para el color de la barra (mismo umbral de 80 % que la HU-60).
export function nivelOcupacion(ocupacion) {
  if (ocupacion.estado === 'sin_franja' || ocupacion.porcentaje == null) return 'sin_franja'
  if (ocupacion.porcentaje >= 100) return 'saturada'
  if (ocupacion.porcentaje >= 80) return 'alerta'
  return 'normal'
}

// Porcentaje de pedidos cancelados, para el detalle de la tarjeta.
export function porcentajeCancelados(cancelaciones, pedidos) {
  if (!pedidos) return 0
  return Math.round((cancelaciones / pedidos) * 100)
}
