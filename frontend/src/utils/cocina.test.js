import { describe, expect, it } from 'vitest'
import { filtrarProductosCocina } from './cocina.js'

const productos = [
  { id: 1, nombre: 'Clásica', categoria: 'Hamburguesas', disponible: false },
  { id: 2, nombre: 'Pepperoni', categoria: 'Pizzas', disponible: true },
  { id: 3, nombre: 'Doble', categoria: 'Hamburguesas', disponible: true },
]

describe('productos de cocina (HU-17)', () => {
  it('busca sin importar tildes ni mayúsculas, por nombre o categoría', () => {
    expect(filtrarProductosCocina(productos, 'CLASICA').map((p) => p.id)).toEqual([1])
    expect(filtrarProductosCocina(productos, 'hambur').map((p) => p.id)).toEqual([3, 1])
    expect(filtrarProductosCocina(productos, 'sushi')).toEqual([])
  })

  it('sin búsqueda muestra todos con los no disponibles al final', () => {
    expect(filtrarProductosCocina(productos, '').map((p) => p.id)).toEqual([2, 3, 1])
  })
})
