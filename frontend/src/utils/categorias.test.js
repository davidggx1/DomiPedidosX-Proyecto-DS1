import { describe, expect, it } from 'vitest'
import { motivoNoEliminar, textoProductos } from './categorias.js'

describe('eliminar categorías (HU-78)', () => {
  it('cuenta los productos en singular y plural', () => {
    expect(textoProductos(0)).toBe('0 productos')
    expect(textoProductos(1)).toBe('1 producto')
    expect(textoProductos(3)).toBe('3 productos')
  })

  it('una categoría sin productos se puede eliminar', () => {
    expect(motivoNoEliminar({ total_productos: 0 })).toBeNull()
    expect(motivoNoEliminar(undefined)).toBeNull()
  })

  it('con productos asociados se bloquea y dice cuántos son', () => {
    expect(motivoNoEliminar({ total_productos: 2 })).toBe(
      'Tiene 2 productos asociados. Muévelos a otra categoría antes de eliminarla.',
    )
    expect(motivoNoEliminar({ total_productos: 1 })).toBe(
      'Tiene 1 producto asociado. Muévelos a otra categoría antes de eliminarla.',
    )
  })
})
