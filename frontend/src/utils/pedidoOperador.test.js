import { describe, expect, it } from 'vitest'
import {
  MAXIMO_POR_LINEA,
  agregarLinea,
  cambiarCantidad,
  itemsParaEnviar,
  lineaLlena,
  mensajeErrorPedido,
  normalizarCantidad,
  precioConTamano,
  quitarLinea,
} from './pedidoOperador.js'

const hamburguesa = { id: 1, nombre: 'Hamburguesa', precio_base: '20000.00' }
const grande = { id: 7, nombre: 'Grande', precio_adicional: '5000.00' }

describe('carrito del operador', () => {
  it('suma el adicional del tamaño al precio', () => {
    expect(precioConTamano(hamburguesa)).toBe(20000)
    expect(precioConTamano(hamburguesa, grande)).toBe(25000)
  })

  it('separa en líneas distintas el mismo producto con otro tamaño', () => {
    let carrito = agregarLinea([], hamburguesa)
    carrito = agregarLinea(carrito, hamburguesa, grande)
    carrito = agregarLinea(carrito, hamburguesa, grande)

    expect(carrito).toHaveLength(2)
    expect(carrito[1]).toMatchObject({ nombre: 'Hamburguesa (Grande)', precio: 25000, cantidad: 2 })
  })

  it('no deja pasar del tope de unidades por línea', () => {
    let carrito = []
    for (let i = 0; i < MAXIMO_POR_LINEA + 3; i++) carrito = agregarLinea(carrito, hamburguesa)
    expect(carrito[0].cantidad).toBe(MAXIMO_POR_LINEA)
    expect(lineaLlena(carrito, hamburguesa)).toBe(true)
    expect(lineaLlena(carrito, hamburguesa, grande)).toBe(false)
  })

  it('cambia la cantidad de una línea dentro de 1 y el tope', () => {
    const carrito = agregarLinea([], hamburguesa)
    const clave = carrito[0].clave
    expect(cambiarCantidad(carrito, clave, '12')[0].cantidad).toBe(12)
    expect(cambiarCantidad(carrito, clave, 0)[0].cantidad).toBe(1)
    expect(cambiarCantidad(carrito, clave, 80)[0].cantidad).toBe(MAXIMO_POR_LINEA)
    expect(cambiarCantidad(carrito, clave, '')).toBe(carrito)
  })

  it('normaliza lo que escribe el operador', () => {
    expect(normalizarCantidad('7.9')).toBe(7)
    expect(normalizarCantidad('abc')).toBeNull()
    expect(normalizarCantidad('  ')).toBeNull()
  })

  it('quita una línea por su clave', () => {
    const carrito = agregarLinea(agregarLinea([], hamburguesa), hamburguesa, grande)
    expect(quitarLinea(carrito, carrito[0].clave)).toEqual([carrito[1]])
  })

  it('envía tamano_id solo cuando la línea tiene tamaño', () => {
    const carrito = agregarLinea(agregarLinea([], hamburguesa), hamburguesa, grande)
    const [sinTamano, conTamano] = itemsParaEnviar(carrito)

    expect(sinTamano).not.toHaveProperty('tamano_id')
    expect(conTamano).toMatchObject({ producto_id: 1, tamano_id: 7, cantidad: 1 })
  })
})

describe('mensajeErrorPedido', () => {
  it('lista el motivo de cada ítem rechazado', () => {
    const datos = {
      detail: 'Algunos ítems no se pueden confirmar.',
      items: [{ indice: 0, nombre: 'Hamburguesa', motivo: 'Solo quedan 2 unidades.' }],
    }
    expect(mensajeErrorPedido(datos)).toBe('Hamburguesa: Solo quedan 2 unidades.')
  })

  it('entiende los errores de campo por ítem y les pone el nombre de la línea', () => {
    const carrito = agregarLinea([], hamburguesa, grande)
    const datos = { items: { 0: { cantidad: ['Ensure this value is less than or equal to 50.'] } } }
    expect(mensajeErrorPedido(datos, carrito)).toBe(
      'Hamburguesa (Grande): Ensure this value is less than or equal to 50.',
    )
    expect(mensajeErrorPedido({ items: [{ cantidad: ['Muy alto.'] }, {}] })).toBe('Muy alto.')
  })

  it('nunca muestra [object Object]', () => {
    expect(mensajeErrorPedido({ algo: { anidado: { mas: ['Texto real.'] } } })).toBe('Texto real.')
    expect(mensajeErrorPedido({ raro: {} })).toBe('Error al registrar el pedido.')
  })

  it('usa detail o el primer error de campo', () => {
    expect(mensajeErrorPedido({ detail: 'Sin sede.' })).toBe('Sin sede.')
    expect(mensajeErrorPedido({ direccion_id: ['Falta la dirección.'] })).toBe('Falta la dirección.')
    expect(mensajeErrorPedido(undefined)).toBe('Error al registrar el pedido.')
  })
})
