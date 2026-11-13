import { describe, expect, it } from 'vitest'
import { nivelOcupacion, porcentajeCancelados, textoTiempoEntrega } from './indicadores.js'

describe('panel de indicadores (HU-70)', () => {
  it('sin entregas muestra 0 y lo aclara', () => {
    expect(textoTiempoEntrega(0, 0)).toEqual({ valor: '0 min', detalle: 'Aún no hay entregas hoy' })
  })

  it('con entregas muestra el promedio y cuántas son', () => {
    expect(textoTiempoEntrega(32, 1).detalle).toBe('Promedio de 1 entrega')
    expect(textoTiempoEntrega(32, 5)).toEqual({ valor: '32 min', detalle: 'Promedio de 5 entregas' })
  })

  it('clasifica la ocupación de la cocina con el umbral de alerta de 80 %', () => {
    expect(nivelOcupacion({ estado: 'disponible', porcentaje: 30 })).toBe('normal')
    expect(nivelOcupacion({ estado: 'disponible', porcentaje: 80 })).toBe('alerta')
    expect(nivelOcupacion({ estado: 'saturada', porcentaje: 100 })).toBe('saturada')
    expect(nivelOcupacion({ estado: 'sin_franja', porcentaje: null })).toBe('sin_franja')
  })

  it('un día sin pedidos no divide por cero', () => {
    expect(porcentajeCancelados(0, 0)).toBe(0)
    expect(porcentajeCancelados(1, 4)).toBe(25)
  })
})
