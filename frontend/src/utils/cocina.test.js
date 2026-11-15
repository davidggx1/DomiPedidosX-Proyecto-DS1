import { describe, expect, it } from 'vitest'
import { filtrarProductosCocina, productosReactivados, validarJustificacion } from './cocina.js'

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

describe('justificación del error de cocina (HU-33)', () => {
  it('es obligatoria y tiene un mínimo y un máximo', () => {
    expect(validarJustificacion('')).toMatch(/Escribe/)
    expect(validarJustificacion('   ')).toMatch(/Escribe/)
    expect(validarJustificacion('abc')).toMatch(/al menos 5/)
    expect(validarJustificacion('x'.repeat(501))).toMatch(/superar 500/)
    expect(validarJustificacion('  Se quemó la carne ')).toBeNull()
  })
})

describe('productos que vuelven a estar disponibles (HU-17)', () => {
  const antes = [
    { id: 1, nombre: 'Clásica', disponible: false },
    { id: 2, nombre: 'Doble', disponible: true },
    { id: 3, nombre: 'Pepperoni', disponible: false },
  ]

  it('devuelve solo los que pasaron de no disponible a disponible', () => {
    const despues = [
      { id: 1, nombre: 'Clásica', disponible: true },
      { id: 2, nombre: 'Doble', disponible: false },
      { id: 3, nombre: 'Pepperoni', disponible: false },
    ]
    expect(productosReactivados(antes, despues)).toEqual(['Clásica'])
  })

  it('no avisa nada en la primera carga', () => {
    expect(productosReactivados(null, antes)).toEqual([])
  })
})
