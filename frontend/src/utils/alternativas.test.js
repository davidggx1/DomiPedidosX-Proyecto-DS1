import { describe, expect, it } from 'vitest'
import {
  coberturaDeAlternativa,
  idsDeProductos,
  ofreceAlternativas,
  textoCambioDeSede,
  textoDistancia,
  textoNoDisponibles,
  trasladarCarrito,
} from './alternativas.js'

const sencilla = { id: 'a', producto: { id: 1, nombre: 'Sencilla' }, cantidad: 1 }
const doble = { id: 'b', producto: { id: 2, nombre: 'Doble' }, cantidad: 2 }
const papas = { id: 'c', producto: { id: 3, nombre: 'Papas' }, cantidad: 1 }

const centro = {
  sede: { id: 7, nombre: 'Centro', direccion: 'Calle 1 # 2-3' },
  distancia_km: 1.25,
  tarifa_domicilio: 2500,
  pedido_minimo: 8000,
  tiempo_estimado: 25,
  cupos_libres: 3,
  no_disponibles: [],
}

describe('sede alterna cuando la sede está bloqueada (HU-62)', () => {
  it('ofrece alternativas si la sede está saturada o sin franja para el cliente', () => {
    expect(ofreceAlternativas({ estado: 'saturada', bloqueado: true })).toBe(true)
    expect(ofreceAlternativas({ estado: 'sin_franja', bloqueado: true })).toBe(true)
  })

  it('no las ofrece si hay cupo, si el personal puede confirmar a mano o sin datos', () => {
    expect(ofreceAlternativas({ estado: 'disponible', bloqueado: false })).toBe(false)
    expect(ofreceAlternativas({ estado: 'sin_franja', bloqueado: false })).toBe(false)
    expect(ofreceAlternativas(null)).toBe(false)
  })

  it('manda al servidor los ids de los productos, sin repetir', () => {
    expect(idsDeProductos([sencilla, doble, { ...doble, id: 'd' }])).toEqual([1, 2])
    expect(idsDeProductos([])).toEqual([])
  })

  it('escribe la distancia con coma decimal', () => {
    expect(textoDistancia(1.25)).toBe('1,25 km')
    expect(textoDistancia(3)).toBe('3 km')
  })

  it('avisa qué productos no tendría la otra sede', () => {
    expect(textoNoDisponibles(centro)).toBeNull()
    expect(textoNoDisponibles({ ...centro, no_disponibles: [{ id: 2, nombre: 'Doble' }] })).toBe(
      '"Doble" no está disponible en esta sede y se quitará de tu carrito.',
    )
    expect(
      textoNoDisponibles({
        ...centro,
        no_disponibles: [{ id: 2, nombre: 'Doble' }, { id: 3, nombre: 'Papas' }],
      }),
    ).toBe('"Doble" y "Papas" no están disponibles en esta sede y se quitará de tu carrito.')
  })

  it('al trasladar el carrito quita lo que la nueva sede no tiene y deja lo demás', () => {
    const alternativa = { ...centro, no_disponibles: [{ id: 2, nombre: 'Doble' }] }
    const { lineas, quitadas } = trasladarCarrito([sencilla, doble, papas], alternativa)
    expect(lineas).toEqual([sencilla, papas])
    expect(quitadas).toEqual([doble])
  })

  it('si la nueva sede tiene todo, el carrito pasa completo', () => {
    const original = [sencilla, doble]
    const { lineas, quitadas } = trasladarCarrito(original, centro)
    expect(lineas).toBe(original)
    expect(quitadas).toEqual([])
  })

  it('la cobertura del checkout pasa a ser la de la nueva sede', () => {
    const cobertura = coberturaDeAlternativa(centro)
    expect(cobertura.cubierto).toBe(true)
    expect(cobertura.mensaje).toBe('Dirección con cobertura confirmada para Centro.')
    expect(cobertura.sede).toEqual({
      id: 7,
      nombre: 'Centro',
      direccion: 'Calle 1 # 2-3',
      distancia_km: 1.25,
      tarifa_domicilio: 2500,
      pedido_minimo: 8000,
      tiempo_estimado: 25,
    })
  })

  it('el aviso del cambio cuenta qué se quitó del carrito', () => {
    expect(textoCambioDeSede(centro, [])).toBe(
      'Cambiaste a la sede Centro. El domicilio, el pedido mínimo y el tiempo de entrega ahora son los de esa sede.',
    )
    expect(textoCambioDeSede(centro, [doble])).toContain('"Doble" no está disponible allí y se quitó de tu carrito.')
    expect(textoCambioDeSede(centro, [doble, papas])).toContain(
      '"Doble" y "Papas" no están disponibles allí y se quitaron de tu carrito.',
    )
  })
})
