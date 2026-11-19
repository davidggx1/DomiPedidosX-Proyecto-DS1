// Utilidades de la página de reportes (HU-71 ventas y HU-72 tiempos)

const DIAS_POR_DEFECTO = 7

function aTextoFecha(fecha) {
  const mes = String(fecha.getMonth() + 1).padStart(2, '0')
  const dia = String(fecha.getDate()).padStart(2, '0')
  return `${fecha.getFullYear()}-${mes}-${dia}`
}

// Últimos 7 días contando hoy, en AAAA-MM-DD (igual que el backend si no se envían fechas)
export function rangoPorDefecto(hoy = new Date()) {
  const desde = new Date(hoy.getFullYear(), hoy.getMonth(), hoy.getDate() - (DIAS_POR_DEFECTO - 1))
  return { desde: aTextoFecha(desde), hasta: aTextoFecha(hoy) }
}

// Mensaje de error del rango, o null si es válido (las fechas AAAA-MM-DD se comparan como texto)
export function validarRango(desde, hasta) {
  if (!desde || !hasta) return 'Elige la fecha de inicio y la de fin.'
  if (desde > hasta) return 'La fecha de inicio no puede ser posterior a la fecha de fin.'
  return null
}

// 12.5 -> "12,5 min"; 75 -> "1 h 15 min"; null -> "—"
export function textoMinutos(minutos) {
  if (minutos === null || minutos === undefined) return '—'
  if (minutos < 60) return `${String(minutos).replace('.', ',')} min`
  const horas = Math.floor(minutos / 60)
  const resto = Math.round(minutos - horas * 60)
  return resto ? `${horas} h ${resto} min` : `${horas} h`
}

// Ancho en % de una barra respecto al valor más alto (mínimo visible 2 % si hay valor)
export function anchoBarra(valor, maximo) {
  if (!valor || !maximo) return 0
  return Math.max(2, Math.round((valor / maximo) * 100))
}

// HU-71 · Agrupaciones del reporte de ventas (mismos valores que el backend)
export const AGRUPACIONES_VENTAS = [
  { valor: 'producto', etiqueta: 'Producto' },
  { valor: 'categoria', etiqueta: 'Categoría' },
  { valor: 'sede', etiqueta: 'Sede' },
  { valor: 'zona', etiqueta: 'Zona de entrega' },
]

// Por producto o categoría se cuentan unidades vendidas; por sede o zona, pedidos
export function cuentaUnidades(agrupar) {
  return agrupar === 'producto' || agrupar === 'categoria'
}

// Filas de "líneas − descuentos + domicilio = total facturado"; los ajustes solo si los hay
export function filasConciliacion(conciliacion) {
  if (!conciliacion) return []
  const filas = [
    { etiqueta: 'Ventas de productos', valor: conciliacion.lineas, signo: '' },
    { etiqueta: 'Descuentos', valor: conciliacion.descuentos, signo: '−' },
    { etiqueta: 'Domicilios', valor: conciliacion.domicilio, signo: '+' },
  ]
  if (Number(conciliacion.ajustes) !== 0) {
    filas.push({ etiqueta: 'Ajustes de facturas', valor: conciliacion.ajustes, signo: '+' })
  }
  filas.push({ etiqueta: 'Total facturado', valor: conciliacion.total, signo: '=', total: true })
  return filas
}
