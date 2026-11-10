import { describe, expect, it } from 'vitest'
import { avisoDeMensaje, duracionAviso } from './avisos.js'

describe('avisos al repartidor (HU-40)', () => {
  it('un mensaje sin aviso no se muestra', () => {
    expect(avisoDeMensaje({ tipo: 'entregas_actualizadas', pedido_id: 3 })).toBeNull()
  })

  it('la asignación lleva al detalle del pedido', () => {
    const aviso = avisoDeMensaje({
      pedido_id: 7,
      aviso: { tipo: 'asignado', numero_pedido: 'P-7', mensaje: 'Te asignaron el pedido P-7.' },
    })
    expect(aviso).toMatchObject({ tipo: 'asignado', titulo: 'Nuevo pedido: P-7', enlace: '/repartidor/entregas/7' })
  })

  it('distingue cancelado de reasignado y no lleva enlace', () => {
    const cancelado = avisoDeMensaje({
      pedido_id: 7,
      aviso: { tipo: 'retirado', motivo: 'cancelado', numero_pedido: 'P-7', mensaje: 'x' },
    })
    const reasignado = avisoDeMensaje({
      pedido_id: 7,
      aviso: { tipo: 'retirado', motivo: 'reasignado', numero_pedido: 'P-7', mensaje: 'x' },
    })
    expect(cancelado.titulo).toBe('Pedido P-7 cancelado')
    expect(reasignado.titulo).toBe('Pedido P-7 retirado')
    expect(cancelado.enlace).toBeNull()
  })

  it('el aviso de asignación dura más en pantalla', () => {
    expect(duracionAviso({ tipo: 'asignado' })).toBeGreaterThan(duracionAviso({ tipo: 'retirado' }))
  })
})
