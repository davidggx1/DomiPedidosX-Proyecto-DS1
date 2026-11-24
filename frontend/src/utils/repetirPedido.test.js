import { describe, expect, it } from 'vitest'
import { avisoRepetir, puedeRepetirse } from './repetirPedido.js'

const sede = { id: 1, nombre: 'Sede Centro' }

describe('repetir pedido (HU-26)', () => {
  it('solo los pedidos cerrados muestran el botón', () => {
    expect(puedeRepetirse({ estado: 'entregado' })).toBe(true)
    expect(puedeRepetirse({ estado: 'cancelado' })).toBe(true)
    expect(puedeRepetirse({ estado: 'en_camino' })).toBe(false)
  })

  it('todo disponible: aviso de éxito con las unidades', () => {
    const aviso = avisoRepetir('P-1', {
      sede,
      lineas: [{ cantidad: 2 }, { cantidad: 1 }],
      no_disponibles: [],
    })
    expect(aviso).toEqual({
      tipo: 'exito',
      titulo: 'Cargamos 3 productos del pedido P-1 en tu carrito, con los precios de hoy.',
      faltantes: [],
      hayLineas: true,
    })
  })

  it('con faltantes: aviso amarillo que los lista', () => {
    const faltantes = [{ nombre: 'Gaseosa', motivo: 'Está agotado.' }]
    const aviso = avisoRepetir('P-1', { sede, lineas: [{ cantidad: 1 }], no_disponibles: faltantes })
    expect(aviso.tipo).toBe('aviso')
    expect(aviso.titulo).toMatch(/Cargamos 1 producto del/)
    expect(aviso.faltantes).toBe(faltantes)
  })

  it('nada disponible: no carga el carrito', () => {
    const aviso = avisoRepetir('P-1', { sede, lineas: [], no_disponibles: [{ nombre: 'X', motivo: 'Y' }] })
    expect(aviso.hayLineas).toBe(false)
    expect(aviso.titulo).toBe('Ningún producto del pedido P-1 está disponible hoy en Sede Centro.')
  })
})
