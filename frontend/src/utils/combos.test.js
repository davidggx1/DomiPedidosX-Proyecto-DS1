import { describe, expect, it } from 'vitest'
import {
  ahorroCombo,
  armarCuerpoCombo,
  contarPorEstadoCombo,
  datosInicialesCombo,
  estadoCombo,
  filtrarCombos,
  productosElegibles,
  sumaIndividual,
  validarCombo,
} from './combos.js'

const PRODUCTOS = [
  { id: 1, nombre: 'Hamburguesa', precio_base: '15000.00' },
  { id: 2, nombre: 'Papas', precio_base: '8000.00' },
  { id: 3, nombre: 'Jugo', precio_base: '6000.00' },
]

const VALIDOS = {
  nombre: 'Combo clásico',
  precio: '20000',
  fecha_inicio: '2026-11-15',
  fecha_vencimiento: '2026-12-15',
  cupo_max_diario: '',
  lineas: { 1: '1', 2: '1' },
}

describe('suma y ahorro', () => {
  it('suma precio × cantidad e ignora cantidades inválidas', () => {
    expect(sumaIndividual({ 1: '1', 2: '2' }, PRODUCTOS)).toBe(31000)
    expect(sumaIndividual({ 1: '0', 2: 'x', 3: '1' }, PRODUCTOS)).toBe(6000)
    expect(sumaIndividual({}, PRODUCTOS)).toBe(0)
  })

  it('el ahorro es suma menos precio; null si no se puede calcular', () => {
    expect(ahorroCombo('20000', 23000)).toBe(3000)
    expect(ahorroCombo('', 23000)).toBeNull()
    expect(ahorroCombo('20000', 0)).toBeNull()
  })
})

describe('validarCombo', () => {
  it('acepta un combo correcto', () => {
    expect(validarCombo(VALIDOS, PRODUCTOS)).toEqual({})
  })

  it('exige nombre y al menos 2 unidades', () => {
    expect(validarCombo({ ...VALIDOS, nombre: ' ' }, PRODUCTOS).nombre).toBeTruthy()
    expect(validarCombo({ ...VALIDOS, lineas: { 1: '1' } }, PRODUCTOS).productos).toBeTruthy()
    expect(validarCombo({ ...VALIDOS, lineas: { 1: '2' }, precio: '25000' }, PRODUCTOS)).toEqual({})
  })

  it('el precio debe ser menor que la suma de los productos', () => {
    expect(validarCombo({ ...VALIDOS, precio: '23000' }, PRODUCTOS).precio).toContain('menor')
    expect(validarCombo({ ...VALIDOS, precio: '25000' }, PRODUCTOS).precio).toContain('menor')
    expect(validarCombo({ ...VALIDOS, precio: '22999.99' }, PRODUCTOS)).toEqual({})
  })

  it('rechaza precio vacío, 0, texto o con más de 2 decimales', () => {
    for (const malo of ['', '0', 'abc', '100.555']) {
      expect(validarCombo({ ...VALIDOS, precio: malo }, PRODUCTOS).precio).toBeTruthy()
    }
    expect(validarCombo({ ...VALIDOS, precio: '19999,50' }, PRODUCTOS)).toEqual({})
  })

  it('valida fechas y cupo', () => {
    expect(validarCombo({ ...VALIDOS, fecha_vencimiento: '' }, PRODUCTOS).fecha_vencimiento).toBeTruthy()
    expect(validarCombo({ ...VALIDOS, fecha_vencimiento: '2026-11-01' }, PRODUCTOS).fecha_vencimiento).toBeTruthy()
    expect(validarCombo({ ...VALIDOS, cupo_max_diario: '0' }, PRODUCTOS).cupo_max_diario).toBeTruthy()
    expect(validarCombo({ ...VALIDOS, cupo_max_diario: '10' }, PRODUCTOS)).toEqual({})
  })
})

describe('cuerpo y valores iniciales', () => {
  it('arma el cuerpo con productos válidos y cupo null si está vacío', () => {
    const cuerpo = armarCuerpoCombo({ ...VALIDOS, nombre: ' Combo ', lineas: { 1: '1', 2: '0', 3: '2' } })
    expect(cuerpo.nombre).toBe('Combo')
    expect(cuerpo.productos).toEqual([
      { producto: 1, cantidad: 1 },
      { producto: 3, cantidad: 2 },
    ])
    expect(cuerpo.cupo_max_diario).toBeNull()
    expect(armarCuerpoCombo({ ...VALIDOS, cupo_max_diario: '15' }).cupo_max_diario).toBe(15)
  })

  it('al editar carga productos y cupo del combo', () => {
    const datos = datosInicialesCombo({
      nombre: 'C', precio: '20000.00', fecha_inicio: '2026-11-15', fecha_vencimiento: '2026-12-01',
      cupo_max_diario: 5, productos_detalle: [{ producto: 1, cantidad: 2 }],
    })
    expect(datos.precio).toBe('20000')
    expect(datos.cupo_max_diario).toBe('5')
    expect(datos.lineas).toEqual({ 1: '2' })
    expect(datosInicialesCombo(null).lineas).toEqual({})
  })

  it('solo ofrece productos activos y acepta respuesta paginada', () => {
    const lista = [{ id: 1, activo: true }, { id: 2, activo: false }, { id: 3 }]
    expect(productosElegibles(lista).map((p) => p.id)).toEqual([1, 3])
    expect(productosElegibles({ results: lista }).map((p) => p.id)).toEqual([1, 3])
    expect(productosElegibles(null)).toEqual([])
  })
})

describe('estados y filtros', () => {
  const lista = [
    { id: 1, activo: true, disponible: true },
    { id: 2, activo: true, disponible: false },
    { id: 3, activo: false, disponible: false },
  ]

  it('un combo inactivo es inactivo aunque tenga productos', () => {
    expect(lista.map(estadoCombo)).toEqual(['disponible', 'no_disponible', 'inactivo'])
  })

  it('cuenta y filtra', () => {
    expect(contarPorEstadoCombo(lista)).toEqual({ todos: 3, disponible: 1, no_disponible: 1, inactivo: 1 })
    expect(filtrarCombos(lista, 'inactivo').map((c) => c.id)).toEqual([3])
    expect(filtrarCombos(lista, 'todos')).toEqual(lista)
  })
})