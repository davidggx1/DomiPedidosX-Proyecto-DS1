import { describe, expect, it } from 'vitest'
import { PASOS_CLIENTE, aplicarEvento, pasosConProgreso } from './seguimiento.js'

describe('pasos de la barra de progreso', () => {
  it('marca los pasos hechos, el actual y los pendientes', () => {
    const historial = [
      { estado: 'pendiente_aprobacion', fecha_hora: '2026-11-06T12:00:00-05:00' },
      { estado: 'recibido', fecha_hora: '2026-11-06T12:02:00-05:00' },
      { estado: 'en_preparacion', fecha_hora: '2026-11-06T12:05:00-05:00' },
    ]
    const pasos = pasosConProgreso('en_preparacion', historial)

    expect(pasos.map((paso) => paso.situacion)).toEqual([
      'hecho', 'hecho', 'actual', 'pendiente', 'pendiente', 'pendiente', 'pendiente',
    ])
    expect(pasos[1].fecha).toBe('2026-11-06T12:02:00-05:00')
    expect(pasos[3].fecha).toBeNull()
  })

  it('un pedido creado ya recibido da por hechos los pasos anteriores', () => {
    const pasos = pasosConProgreso('recibido', [{ estado: 'recibido', fecha_hora: 'x' }])
    expect(pasos[0]).toMatchObject({ situacion: 'hecho', fecha: null })
    expect(pasos[1].situacion).toBe('actual')
  })

  it('entregado deja todos los pasos hechos', () => {
    const pasos = pasosConProgreso('entregado', [])
    expect(pasos.every((paso) => paso.situacion === 'hecho')).toBe(true)
    expect(pasos).toHaveLength(PASOS_CLIENTE.length)
  })
})

describe('eventos en tiempo real', () => {
  const seguimiento = { estado: 'recibido', estado_nombre: 'Recibido', motivo_cancelacion: '', historial: [] }

  it('un cambio de estado actualiza el estado y agrega el paso al historial', () => {
    const evento = {
      tipo: 'estado_pedido_cambiado', estado: 'en_preparacion', estado_nombre: 'En preparación',
      fecha_hora: '2026-11-06T12:05:00-05:00',
    }
    const nuevo = aplicarEvento(seguimiento, evento)
    expect(nuevo.estado).toBe('en_preparacion')
    expect(nuevo.historial).toEqual([
      { estado: 'en_preparacion', estado_nombre: 'En preparación', fecha_hora: '2026-11-06T12:05:00-05:00' },
    ])
  })

  it('la cancelación trae su motivo', () => {
    const nuevo = aplicarEvento(seguimiento, {
      tipo: 'estado_pedido_cambiado', estado: 'cancelado', estado_nombre: 'Cancelado',
      motivo_cancelacion: 'Se agotó el pan', fecha_hora: 'x',
    })
    expect(nuevo.motivo_cancelacion).toBe('Se agotó el pan')
  })

  it('un evento repetido u otro tipo de mensaje no cambia nada', () => {
    expect(aplicarEvento(seguimiento, { tipo: 'estado_pedido_cambiado', estado: 'recibido' })).toBe(seguimiento)
    expect(aplicarEvento(seguimiento, { tipo: 'otro' })).toBe(seguimiento)
  })
})
