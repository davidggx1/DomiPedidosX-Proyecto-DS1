import { describe, expect, it } from 'vitest'
import { detalleFila, estaAgotado } from './existencias.js'

describe('existencias', () => {
  it('muestra la categoría y el tipo de control del producto', () => {
    const fila = { categoria_nombre: 'Bebidas', tipo_control_stock: 'NINGUNO' }
    expect(detalleFila('productos', fila)).toBe('Bebidas · Sin control de stock')
  })

  it('un producto marcado no disponible (agotado por cocina) se ve agotado aunque tenga stock', () => {
    const fila = { stock_actual: 50, disponible: false, tipo_control_stock: 'NINGUNO' }
    expect(estaAgotado('productos', fila)).toBe(true)
  })

  it('con stock en 0 solo se agota si se controla por unidades', () => {
    expect(estaAgotado('productos', { stock_actual: 0, disponible: true, tipo_control_stock: 'PRODUCTO' })).toBe(true)
    expect(estaAgotado('productos', { stock_actual: 0, disponible: true, tipo_control_stock: 'NINGUNO' })).toBe(false)
  })
})
