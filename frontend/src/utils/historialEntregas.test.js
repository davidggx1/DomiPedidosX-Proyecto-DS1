import { describe, expect, it } from 'vitest'
import { agruparPorDia, atajosFecha, fechaLocal, nombreDia } from './historialEntregas.js'

const HOY = new Date(2026, 10, 24, 21, 30) // 24 nov 2026, 9:30 p. m. local

describe('historial de entregas (HU-46)', () => {
  it('usa la fecha local, no la de UTC', () => {
    expect(fechaLocal(HOY)).toBe('2026-11-24')
  })

  it('atajos de fechas', () => {
    expect(atajosFecha(HOY)).toEqual([
      { etiqueta: 'Hoy', desde: '2026-11-24', hasta: '2026-11-24' },
      { etiqueta: 'Ayer', desde: '2026-11-23', hasta: '2026-11-23' },
      { etiqueta: 'Últimos 7 días', desde: '2026-11-18', hasta: '2026-11-24' },
    ])
  })

  it('nombre del día', () => {
    expect(nombreDia('2026-11-24', HOY)).toBe('Hoy')
    expect(nombreDia('2026-11-23', HOY)).toBe('Ayer')
    expect(nombreDia('2026-11-17', HOY)).toMatch(/17/)
  })

  it('agrupa por día respetando el orden', () => {
    const entregas = [
      { id: 3, entregado_en: new Date(2026, 10, 24, 18).toISOString() },
      { id: 2, entregado_en: new Date(2026, 10, 24, 9).toISOString() },
      { id: 1, entregado_en: new Date(2026, 10, 23, 22).toISOString() },
    ]
    const grupos = agruparPorDia(entregas)
    expect(grupos.map((g) => [g.dia, g.entregas.map((e) => e.id)])).toEqual([
      ['2026-11-24', [3, 2]],
      ['2026-11-23', [1]],
    ])
  })
})
