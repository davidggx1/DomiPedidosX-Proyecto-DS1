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

// HU-74 · Patrones de demanda: el backend numera los días como ISO (1 = lunes ... 7 = domingo)
export const DIAS_CORTOS = { 1: 'Lun', 2: 'Mar', 3: 'Mié', 4: 'Jue', 5: 'Vie', 6: 'Sáb', 7: 'Dom' }

export const MEDIDAS_DEMANDA = [
  { valor: 'pedidos', etiqueta: 'Pedidos' },
  { valor: 'ventas', etiqueta: 'Ventas' },
]

// 18 -> "18:00–19:00"; 23 -> "23:00–24:00"
export function textoHora(hora) {
  const dos = (n) => String(n).padStart(2, '0')
  return `${dos(hora)}:00–${dos(hora + 1)}:00`
}

// Qué tan fuerte se pinta una celda del mapa de calor, de 0 a 1. Una celda con algo de
// demanda nunca baja de 0,15 para que no se confunda con una vacía.
export function intensidadCelda(valor, maximo) {
  const numero = Number(valor)
  if (!numero || !maximo) return 0
  return Math.max(0.15, Math.round((numero / maximo) * 100) / 100)
}

const MESES_CORTOS = ['ene', 'feb', 'mar', 'abr', 'may', 'jun', 'jul', 'ago', 'sep', 'oct', 'nov', 'dic']

// Fechas de una celda del mapa de calor (AAAA-MM-DD) en corto: ["2026-11-06", "2026-11-13"] -> "6 nov, 13 nov".
// Con muchas fechas muestra las 3 primeras y cuántas faltan, para que el texto no sea eterno
export function textoFechasCortas(fechas = [], maximo = 3) {
  const cortas = fechas.slice(0, maximo).map((fecha) => {
    const [, mes, dia] = fecha.split('-').map(Number)
    return `${dia} ${MESES_CORTOS[mes - 1]}`
  })
  const resto = fechas.length - cortas.length
  return resto > 0 ? `${cortas.join(', ')} y ${resto} más` : cortas.join(', ')
}
