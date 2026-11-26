import { describe, expect, it } from 'vitest'
import { buscarSede, nombreSede } from './sedeCarrito.js'

const sedes = [
  { id: 1, nombre: 'Sede Centro', barrio: 'San Pedro' },
  { id: 2, nombre: 'Sede Sur', barrio: '' },
]

describe('nombreSede', () => {
  it('une el nombre y el barrio como en el menú', () => {
    expect(nombreSede(sedes[0])).toBe('Sede Centro · San Pedro')
  })

  it('sin barrio muestra solo el nombre', () => {
    expect(nombreSede(sedes[1])).toBe('Sede Sur')
  })

  it('sin sede no muestra nada', () => {
    expect(nombreSede(null)).toBe('')
  })
})

describe('buscarSede', () => {
  it('encuentra la sede aunque el id venga como texto', () => {
    expect(buscarSede(sedes, '2')).toBe(sedes[1])
  })

  it('devuelve null si no hay sede o no existe', () => {
    expect(buscarSede(sedes, null)).toBeNull()
    expect(buscarSede(sedes, 9)).toBeNull()
    expect(buscarSede(undefined, 1)).toBeNull()
  })
})
