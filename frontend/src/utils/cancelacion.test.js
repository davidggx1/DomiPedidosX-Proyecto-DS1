import { describe, expect, it } from 'vitest'
import { MOTIVO_MAXIMO, armarMotivo, validarMotivo } from './cancelacion.js'

describe('armarMotivo', () => {
  it('usa la etiqueta del motivo y le suma el detalle', () => {
    expect(armarMotivo('agotado')).toBe('Producto agotado')
    expect(armarMotivo('agotado', '  no hay   pan ')).toBe('Producto agotado: no hay pan')
  })

  it('con "otro" solo envía el detalle', () => {
    expect(armarMotivo('otro', 'La moto se varó')).toBe('La moto se varó')
  })
})

describe('validarMotivo', () => {
  it('exige elegir un motivo', () => {
    expect(validarMotivo('')).toEqual({ codigo: 'Elige el motivo de la cancelación.' })
  })

  it('un motivo de la lista no necesita detalle', () => {
    expect(validarMotivo('cliente')).toEqual({})
  })

  it('"otro" necesita un detalle de al menos 5 caracteres', () => {
    expect(validarMotivo('otro', 'abc')).toHaveProperty('detalle')
    expect(validarMotivo('otro', 'La moto se varó')).toEqual({})
  })

  it('no deja pasar del máximo del backend', () => {
    expect(validarMotivo('incidente', 'x'.repeat(MOTIVO_MAXIMO))).toHaveProperty('detalle')
  })
})
