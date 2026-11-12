import { describe, expect, it } from 'vitest'
import {
  actualizarCantidad,
  agregarLinea,
  bloqueosPorInsumo,
  claveCarrito,
  cantidadArticulos,
  claveVariante,
  domicilioCarrito,
  domicilioDeZona,
  eliminarLinea,
  lineaParaValidar,
  precioUnitario,
  reemplazarLinea,
  subtotalCarrito,
  subtotalLinea,
  totalCarrito,
} from './carrito.js'

const producto = { id: 1, nombre: 'Hamburguesa', imagen: null, precio_base: '20000.00' }
const personal = { id: 10, nombre: 'Personal', precio_adicional: '0.00' }
const doble = { id: 11, nombre: 'Doble', precio_adicional: '8000.00' }
const queso = { adicion: 5, nombre: 'Queso extra', precio: '3000.00' }
const cebolla = { id: 7, nombre: 'Cebolla' }

function linea(id, cambios = {}) {
  const base = { id, producto, tamano: personal, adiciones: [], exclusiones: [], cantidad: 1 }
  const datos = { ...base, ...cambios }
  return { ...datos, precio_unitario: String(precioUnitario(datos)) }
}

describe('precio de una línea', () => {
  it('suma base, tamaño y adiciones por su cantidad', () => {
    const datos = { producto, tamano: doble, adiciones: [{ ...queso, cantidad: 2 }] }
    expect(precioUnitario(datos)).toBe(34000)
  })

  it('el subtotal multiplica el precio unitario por la cantidad', () => {
    expect(subtotalLinea(linea('a', { cantidad: 3 }))).toBe(60000)
  })
})

describe('líneas distintas del mismo producto', () => {
  it('distinto tamaño, adiciones o exclusiones son líneas separadas', () => {
    let lineas = []
    lineas = agregarLinea(lineas, linea('a'))
    lineas = agregarLinea(lineas, linea('b', { tamano: doble }))
    lineas = agregarLinea(lineas, linea('c', { adiciones: [{ ...queso, cantidad: 1 }] }))
    lineas = agregarLinea(lineas, linea('d', { exclusiones: [cebolla] }))

    expect(lineas).toHaveLength(4)
    expect(subtotalCarrito(lineas)).toBe(20000 + 28000 + 23000 + 20000)
  })

  it('la misma configuración suma la cantidad en la línea existente', () => {
    let lineas = agregarLinea([], linea('a', { cantidad: 1, exclusiones: [cebolla] }))
    lineas = agregarLinea(lineas, linea('b', { cantidad: 2, exclusiones: [cebolla] }))

    expect(lineas).toHaveLength(1)
    expect(lineas[0].id).toBe('a')
    expect(lineas[0].cantidad).toBe(3)
    expect(cantidadArticulos(lineas)).toBe(3)
  })

  it('el orden de las adiciones no cambia la variante', () => {
    const tocineta = { adicion: 6, nombre: 'Tocineta', precio: '4000.00', cantidad: 1 }
    const una = { producto, tamano: personal, adiciones: [{ ...queso, cantidad: 1 }, tocineta] }
    const otra = { producto, tamano: personal, adiciones: [tocineta, { ...queso, cantidad: 1 }] }
    expect(claveVariante(una)).toBe(claveVariante(otra))
  })
})

describe('modificar o eliminar recalcula el subtotal', () => {
  const inicial = [linea('a'), linea('b', { tamano: doble })]

  it('cambiar la cantidad', () => {
    const lineas = actualizarCantidad(inicial, 'b', 2)
    expect(subtotalCarrito(lineas)).toBe(20000 + 56000)
  })

  it('cantidad 0 elimina la línea', () => {
    expect(actualizarCantidad(inicial, 'a', 0)).toHaveLength(1)
  })

  it('eliminar una línea', () => {
    const lineas = eliminarLinea(inicial, 'a')
    expect(lineas.map((item) => item.id)).toEqual(['b'])
    expect(subtotalCarrito(lineas)).toBe(28000)
  })

  it('editar una línea cambia su precio y conserva su id', () => {
    const editada = linea('nueva', { adiciones: [{ ...queso, cantidad: 2 }] })
    const lineas = reemplazarLinea(inicial, 'a', editada)
    expect(lineas[0].id).toBe('a')
    expect(subtotalCarrito(lineas)).toBe(26000 + 28000)
  })

  it('si la edición la deja igual a otra línea, se fusionan', () => {
    const lineas = reemplazarLinea(inicial, 'a', linea('nueva', { tamano: doble }))
    expect(lineas).toHaveLength(1)
    expect(lineas[0]).toMatchObject({ id: 'b', cantidad: 2 })
  })
})

it('arma los datos que valida el backend', () => {
  const datos = linea('a', {
    tamano: doble,
    adiciones: [{ ...queso, cantidad: 2 }, { adicion: 6, nombre: 'Tocineta', precio: '4000', cantidad: 0 }],
    exclusiones: [cebolla],
    cantidad: 2,
  })
  expect(lineaParaValidar(datos)).toEqual({
    producto: 1,
    tamano: 11,
    adiciones: [{ adicion: 5, cantidad: 2 }],
    exclusiones: [7],
    cantidad: 2,
  })
})

describe('ingredientes base y adiciones del mismo insumo', () => {
  const ingredientes = [
    { id: 1, nombre: 'Queso', insumo: 30 },
    { id: 2, nombre: 'Tocineta', insumo: 40 },
    { id: 3, nombre: 'Cebolla', insumo: 50 },
  ]
  const adiciones = [
    { adicion: 5, nombre: 'Queso extra', insumo: 30 },
    { adicion: 6, nombre: 'Tocineta extra', insumo: 40 },
  ]

  it('agregar una adición bloquea quitar su ingrediente base', () => {
    const bloqueos = bloqueosPorInsumo({ ingredientes, adiciones, cantidades: { 5: 1 }, exclusiones: new Set() })
    expect(Object.keys(bloqueos.ingredientes)).toEqual(['1'])
    expect(bloqueos.ingredientes[1].nombre).toBe('Queso extra')
    expect(bloqueos.adiciones).toEqual({})
  })

  it('con las dos adiciones se bloquean los dos ingredientes', () => {
    const bloqueos = bloqueosPorInsumo({ ingredientes, adiciones, cantidades: { 5: 1, 6: 1 }, exclusiones: new Set() })
    expect(Object.keys(bloqueos.ingredientes)).toEqual(['1', '2'])
  })

  it('quitar ingredientes base bloquea sus adiciones', () => {
    const bloqueos = bloqueosPorInsumo({ ingredientes, adiciones, cantidades: {}, exclusiones: new Set([1, 2]) })
    expect(Object.keys(bloqueos.adiciones)).toEqual(['5', '6'])
    expect(bloqueos.ingredientes).toEqual({})
  })

  it('quitar un ingrediente sin adición no bloquea nada', () => {
    const bloqueos = bloqueosPorInsumo({ ingredientes, adiciones, cantidades: {}, exclusiones: new Set([3]) })
    expect(bloqueos).toEqual({ adiciones: {}, ingredientes: {} })
  })
})

describe('un carrito por cuenta', () => {
  it('cada cliente tiene su propia clave', () => {
    const x = claveCarrito({ rol: 'cliente', email: 'x@correo.com' })
    const y = claveCarrito({ rol: 'cliente', email: 'y@correo.com' })
    expect(x).not.toBe(y)
  })

  it('la clave no depende de mayúsculas en el correo', () => {
    expect(claveCarrito({ rol: 'cliente', email: 'X@Correo.com' })).toBe(
      claveCarrito({ rol: 'cliente', email: 'x@correo.com' }),
    )
  })

  it('sin sesión o con otro rol no hay carrito', () => {
    expect(claveCarrito(null)).toBeNull()
    expect(claveCarrito({ rol: 'operador', email: 'op@correo.com' })).toBeNull()
  })
})

describe('domicilio según la zona (HU-22)', () => {
  it('usa la tarifa de la zona y no la provisional de 4000', () => {
    expect(domicilioDeZona(20000, 3000)).toBe(3000)
    expect(domicilioDeZona(20000, 6500)).toBe(6500)
  })

  it('acepta la tarifa como texto o decimal', () => {
    expect(domicilioDeZona(20000, '3500.00')).toBe(3500)
  })

  it('una zona con domicilio gratis cobra 0', () => {
    expect(domicilioDeZona(20000, 0)).toBe(0)
  })

  it('sin subtotal no se cobra domicilio', () => {
    expect(domicilioDeZona(0, 3000)).toBe(0)
  })

  it('sin zona conocida no inventa una tarifa', () => {
    expect(domicilioDeZona(20000, null)).toBeNull()
    expect(domicilioDeZona(20000, undefined)).toBeNull()
  })

  it('el total es subtotal más domicilio', () => {
    expect(totalCarrito(20000, domicilioDeZona(20000, 3000))).toBe(23000)
  })

  it('domicilioCarrito conserva su comportamiento anterior', () => {
    expect(domicilioCarrito(20000)).toBe(4000)
    expect(domicilioCarrito(0)).toBe(0)
  })
})