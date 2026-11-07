import { describe, expect, it } from 'vitest'
import { ESTADOS_PEDIDO, FASES_PEDIDO, datosEstado, pedidosActivos } from './estadosPedido.js'

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

describe('fases del resumen del día', () => {
  it('cada estado está en una sola fase', () => {
    const estados = FASES_PEDIDO.flatMap((fase) => fase.estados)
    expect(estados.sort()).toEqual(Object.keys(ESTADOS_PEDIDO).sort())
  })

  it('los activos no cuentan entregados ni cancelados', () => {
    const porEstado = { pendiente_aprobacion: 1, en_preparacion: 2, en_camino: 1, entregado: 5, cancelado: 3 }
    expect(pedidosActivos(porEstado)).toBe(4)
  })
})
