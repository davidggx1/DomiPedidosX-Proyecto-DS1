import { describe, expect, it } from 'vitest'
import { faltanteMinimo } from './pedidoMinimo.js'

describe('faltanteMinimo', () => {
  it('informa cuánto falta cuando el subtotal no alcanza', () => {
    expect(faltanteMinimo(8000, 10000)).toBe(2000)
    expect(faltanteMinimo(8000, '10000.00')).toBe(2000)
  })

  it('al igualar o superar el mínimo no falta nada', () => {
    expect(faltanteMinimo(10000, 10000)).toBe(0)
    expect(faltanteMinimo(15000, 10000)).toBe(0)
  })

  it('mínimo 0, nulo o desconocido equivale a sin mínimo', () => {
    expect(faltanteMinimo(1000, 0)).toBe(0)
    expect(faltanteMinimo(1000, null)).toBe(0)
    expect(faltanteMinimo(1000, undefined)).toBe(0)
  })
})