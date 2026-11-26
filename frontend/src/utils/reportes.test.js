import { describe, expect, it } from 'vitest'
import {
  anchoBarra,
  cuentaUnidades,
  filasConciliacion,
  intensidadCelda,
  rangoPorDefecto,
  textoFechasCortas,
  textoHora,
  textoMinutos,
  validarRango,
} from './reportes.js'

describe('reportes (HU-72)', () => {
  it('el rango por defecto son los últimos 7 días contando hoy', () => {
    expect(rangoPorDefecto(new Date(2026, 10, 13))).toEqual({ desde: '2026-11-07', hasta: '2026-11-13' })
    expect(rangoPorDefecto(new Date(2026, 0, 3))).toEqual({ desde: '2025-12-28', hasta: '2026-01-03' })
  })

  it('valida el rango de fechas', () => {
    expect(validarRango('', '2026-11-13')).toBe('Elige la fecha de inicio y la de fin.')
    expect(validarRango('2026-11-14', '2026-11-13')).toBe('La fecha de inicio no puede ser posterior a la fecha de fin.')
    expect(validarRango('2026-11-13', '2026-11-13')).toBeNull()
  })

  it('muestra los minutos de forma legible', () => {
    expect(textoMinutos(null)).toBe('—')
    expect(textoMinutos(0)).toBe('0 min')
    expect(textoMinutos(12.5)).toBe('12,5 min')
    expect(textoMinutos(60)).toBe('1 h')
    expect(textoMinutos(75.4)).toBe('1 h 15 min')
  })

  it('calcula el ancho de las barras', () => {
    expect(anchoBarra(null, 10)).toBe(0)
    expect(anchoBarra(5, 0)).toBe(0)
    expect(anchoBarra(5, 10)).toBe(50)
    expect(anchoBarra(0.1, 100)).toBe(2)
  })
})

describe('reportes de ventas (HU-71)', () => {
  const conciliacion = {
    lineas: '106000.00', descuentos: '4400.00', domicilio: '3000.00', ajustes: '0.00', total: '104600.00',
  }

  it('la conciliación termina en el total facturado y oculta ajustes en cero', () => {
    const filas = filasConciliacion(conciliacion)
    expect(filas.map((f) => f.etiqueta)).toEqual([
      'Ventas de productos', 'Descuentos', 'Domicilios', 'Total facturado',
    ])
    expect(filas.at(-1)).toMatchObject({ valor: '104600.00', total: true })
  })

  it('muestra los ajustes cuando las facturas no cuadran con las líneas', () => {
    const filas = filasConciliacion({ ...conciliacion, ajustes: '60000.00' })
    expect(filas.map((f) => f.etiqueta)).toContain('Ajustes de facturas')
  })

  it('sin conciliación (por sede o zona) no hay filas', () => {
    expect(filasConciliacion(null)).toEqual([])
  })

  it('cuenta unidades solo por producto o categoría', () => {
    expect(cuentaUnidades('producto')).toBe(true)
    expect(cuentaUnidades('zona')).toBe(false)
  })
})

describe('patrones de demanda (HU-74)', () => {
  it('escribe la franja de una hora', () => {
    expect(textoHora(0)).toBe('00:00–01:00')
    expect(textoHora(18)).toBe('18:00–19:00')
    expect(textoHora(23)).toBe('23:00–24:00')
  })

  it('la intensidad va de 0 a 1 según el máximo', () => {
    expect(intensidadCelda(10, 10)).toBe(1)
    expect(intensidadCelda(5, 10)).toBe(0.5)
    expect(intensidadCelda('30000.00', 60000)).toBe(0.5)
  })

  it('una celda vacía es 0 y una con poca demanda no baja de 0,15', () => {
    expect(intensidadCelda(0, 10)).toBe(0)
    expect(intensidadCelda(5, 0)).toBe(0)
    expect(intensidadCelda(1, 100)).toBe(0.15)
  })
})

describe('fechas de una celda (HU-74)', () => {
  it('escribe las fechas en corto', () => {
    expect(textoFechasCortas(['2026-11-06'])).toBe('6 nov')
    expect(textoFechasCortas(['2026-11-06', '2026-12-13'])).toBe('6 nov, 13 dic')
  })

  it('con muchas fechas muestra las primeras y cuántas faltan', () => {
    expect(textoFechasCortas(['2026-11-02', '2026-11-09', '2026-11-16', '2026-11-23', '2026-11-30'])).toBe(
      '2 nov, 9 nov, 16 nov y 2 más',
    )
  })

  it('sin fechas no escribe nada', () => {
    expect(textoFechasCortas([])).toBe('')
    expect(textoFechasCortas()).toBe('')
  })
})
