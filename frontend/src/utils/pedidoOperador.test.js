import { describe, expect, it } from 'vitest'
import {
  agregarLinea,
  itemsParaEnviar,
  mensajeErrorPedido,
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

  it('usa detail o el primer error de campo', () => {
    expect(mensajeErrorPedido({ detail: 'Sin sede.' })).toBe('Sin sede.')
    expect(mensajeErrorPedido({ direccion_id: ['Falta la dirección.'] })).toBe('Falta la dirección.')
    expect(mensajeErrorPedido(undefined)).toBe('Error al registrar el pedido.')
  })
})
