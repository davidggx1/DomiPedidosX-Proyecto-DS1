import { describe, expect, it } from 'vitest'
import { anchoBarra, rangoPorDefecto, textoMinutos, validarRango } from './reportes.js'

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
