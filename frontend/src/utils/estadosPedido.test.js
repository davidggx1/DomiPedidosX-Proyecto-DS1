import { describe, expect, it } from 'vitest'
import { ESTADOS_PEDIDO, datosEstado } from './estadosPedido.js'

describe('estados del pedido', () => {
  it('tiene los 8 estados del backend', () => {
    expect(Object.keys(ESTADOS_PEDIDO)).toEqual([
      'pendiente_aprobacion',
      'recibido',
      'en_preparacion',
      'listo_despacho',
      'recogido',
      'en_camino',
      'entregado',
      'cancelado',
    ])
  })

  it('da el nombre y el color de un estado', () => {
    expect(datosEstado('en_camino')).toEqual({ etiqueta: 'En camino', clases: 'border-texto text-texto' })
    expect(datosEstado('cancelado').clases).toContain('text-error')
  })

  it('un estado desconocido muestra su código sin romper', () => {
    expect(datosEstado('nuevo_estado').etiqueta).toBe('nuevo_estado')
  })
})
