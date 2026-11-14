import { describe, expect, it } from 'vitest'
import {
  claseEstado,
  contarPorEstado,
  filtrarPorEstado,
  nombreCompleto,
  porcentajeAvance,
  textoAvance,
  textoCarga,
} from './estadoRepartidores.js'

const ana = { id: 1, nombres: 'Ana', apellidos: 'Pérez', estado: 'disponible', carga: 0 }
const beto = { id: 2, nombres: 'Beto', apellidos: 'Ruiz', estado: 'no_disponible', carga: 0 }
const carla = { id: 3, nombres: 'Carla', apellidos: 'Gil', estado: 'en_entrega', carga: 2 }
const luis = { id: 4, nombres: 'Luis', apellidos: 'Mora', estado: 'en_entrega', carga: 1 }
const todos = [ana, beto, carla, luis]

describe('contadores por estado', () => {
  it('cuenta cada estado y el total', () => {
    expect(contarPorEstado(todos)).toEqual({ todos: 4, disponible: 1, en_entrega: 2, no_disponible: 1 })
  })

  it('sin repartidores todo está en cero', () => {
    expect(contarPorEstado([])).toEqual({ todos: 0, disponible: 0, en_entrega: 0, no_disponible: 0 })
  })

  it('ignora un estado desconocido en los contadores por estado', () => {
    const conteo = contarPorEstado([{ id: 9, estado: 'raro' }])
    expect(conteo).toEqual({ todos: 1, disponible: 0, en_entrega: 0, no_disponible: 0 })
  })
})

describe('filtro por estado', () => {
  it('"todos" o sin filtro devuelve la lista completa', () => {
    expect(filtrarPorEstado(todos, 'todos')).toEqual(todos)
    expect(filtrarPorEstado(todos, undefined)).toEqual(todos)
  })

  it('deja solo los repartidores del estado pedido', () => {
    expect(filtrarPorEstado(todos, 'en_entrega').map((r) => r.id)).toEqual([3, 4])
    expect(filtrarPorEstado(todos, 'disponible').map((r) => r.id)).toEqual([1])
    expect(filtrarPorEstado(todos, 'no_disponible').map((r) => r.id)).toEqual([2])
  })
})

describe('textos', () => {
  it('carga de trabajo', () => {
    expect(textoCarga(0)).toBe('Sin entregas')
    expect(textoCarga(undefined)).toBe('Sin entregas')
    expect(textoCarga(1)).toBe('1 entrega')
    expect(textoCarga(3)).toBe('3 entregas')
  })

  it('nombre completo', () => {
    expect(nombreCompleto(ana)).toBe('Ana Pérez')
  })

  it('cada estado tiene su color', () => {
    expect(claseEstado('disponible')).toContain('exito')
    expect(claseEstado('en_entrega')).toContain('aviso')
    expect(claseEstado('no_disponible')).toContain('borde')
  })
})

describe('avance del pedido', () => {
  it('porcentaje según el paso', () => {
    expect(porcentajeAvance({ paso: 1, total: 4 })).toBe(25)
    expect(porcentajeAvance({ paso: 2, total: 4 })).toBe(50)
    expect(porcentajeAvance({ paso: 3, total: 4 })).toBe(75)
    expect(porcentajeAvance({ paso: 4, total: 4 })).toBe(100)
  })

  it('paso 0 o sin total es 0 y nunca pasa de 100', () => {
    expect(porcentajeAvance({ paso: 0, total: 4 })).toBe(0)
    expect(porcentajeAvance({ paso: 2, total: 0 })).toBe(0)
    expect(porcentajeAvance({ paso: 9, total: 4 })).toBe(100)
  })

  it('texto del paso', () => {
    expect(textoAvance({ paso: 2, total: 4 })).toBe('Paso 2 de 4')
    expect(textoAvance({ paso: 0, total: 4 })).toBe('En proceso')
  })
})