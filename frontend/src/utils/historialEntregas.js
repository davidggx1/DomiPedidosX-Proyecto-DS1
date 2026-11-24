// HU-46 · Historial de entregas del repartidor: atajos de fechas y agrupación por día.

// Fecha local en AAAA-MM-DD (no toISOString: en Colombia daría el día siguiente de noche)
export function fechaLocal(fecha) {
  const mes = String(fecha.getMonth() + 1).padStart(2, '0')
  const dia = String(fecha.getDate()).padStart(2, '0')
  return `${fecha.getFullYear()}-${mes}-${dia}`
}

function haceDias(hoy, dias) {
  return fechaLocal(new Date(hoy.getFullYear(), hoy.getMonth(), hoy.getDate() - dias))
}

// Botones rápidos del filtro
export function atajosFecha(hoy = new Date()) {
  return [
    { etiqueta: 'Hoy', desde: haceDias(hoy, 0), hasta: haceDias(hoy, 0) },
    { etiqueta: 'Ayer', desde: haceDias(hoy, 1), hasta: haceDias(hoy, 1) },
    { etiqueta: 'Últimos 7 días', desde: haceDias(hoy, 6), hasta: haceDias(hoy, 0) },
  ]
}

// "Hoy", "Ayer" o "lunes 17 de noviembre"
export function nombreDia(dia, hoy = new Date()) {
  if (dia === haceDias(hoy, 0)) return 'Hoy'
  if (dia === haceDias(hoy, 1)) return 'Ayer'
  const [anio, mes, numero] = dia.split('-').map(Number)
  return new Date(anio, mes - 1, numero).toLocaleDateString('es-CO', {
    weekday: 'long',
    day: 'numeric',
    month: 'long',
  })
}

// Las entregas llegan de la más reciente a la más vieja: se agrupan por día local en ese orden
export function agruparPorDia(entregas) {
  const grupos = []
  for (const entrega of entregas) {
    const dia = fechaLocal(new Date(entrega.entregado_en))
    const ultimo = grupos.at(-1)
    if (ultimo?.dia === dia) ultimo.entregas.push(entrega)
    else grupos.push({ dia, entregas: [entrega] })
  }
  return grupos
}
