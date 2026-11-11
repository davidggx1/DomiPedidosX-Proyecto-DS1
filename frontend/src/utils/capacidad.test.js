import { describe, expect, it } from 'vitest'
import { errorDeCapacidad, interpretarCapacidad } from './capacidad.js'

const base = { sede: 1, activos: 0, maximo: 5, requiere_confirmacion: false }

describe('estado de capacidad de la sede (HU-61)', () => {
  it('sin datos no bloquea ni avisa', () => {
    expect(interpretarCapacidad(null)).toEqual({
      bloqueado: false,
      requiereConfirmacion: false,
      aviso: null,
    })
  })

  it('con cupo disponible no bloquea ni avisa', () => {
    const r = interpretarCapacidad({ ...base, estado: 'disponible', bloqueado: false, mensaje: 'Cupos' })
    expect(r.bloqueado).toBe(false)
    expect(r.aviso).toBeNull()
  })

  it('saturada bloquea y muestra el mensaje del servidor', () => {
    const mensaje = 'La sede Norte alcanzó el 100% de su capacidad (5/5).'
    const r = interpretarCapacidad({ ...base, activos: 5, estado: 'saturada', bloqueado: true, mensaje })
    expect(r).toEqual({ bloqueado: true, requiereConfirmacion: false, aviso: { tipo: 'error', texto: mensaje } })
  })

  it('sin franja bloquea al cliente con un error', () => {
    const r = interpretarCapacidad({ ...base, estado: 'sin_franja', bloqueado: true, mensaje: 'Sin franja' })
    expect(r.bloqueado).toBe(true)
    expect(r.requiereConfirmacion).toBe(false)
    expect(r.aviso.tipo).toBe('error')
  })

  it('sin franja avisa al operador y le deja confirmar a mano', () => {
    const r = interpretarCapacidad({
      ...base,
      estado: 'sin_franja',
      bloqueado: false,
      requiere_confirmacion: true,
      mensaje: 'Sin franja',
    })
    expect(r.bloqueado).toBe(false)
    expect(r.requiereConfirmacion).toBe(true)
    expect(r.aviso.tipo).toBe('aviso')
  })
})

describe('error de capacidad al enviar el pedido (HU-61)', () => {
  const error = (status, datos) => ({ response: { status, data: datos } })

  it('reconoce los dos códigos de capacidad con 409', () => {
    const saturada = { codigo: 'capacidad_maxima_alcanzada', detail: 'x' }
    const sinFranja = { codigo: 'franja_no_configurada', detail: 'y' }
    expect(errorDeCapacidad(error(409, saturada))).toBe(saturada)
    expect(errorDeCapacidad(error(409, sinFranja))).toBe(sinFranja)
  })

  it('ignora otros errores', () => {
    expect(errorDeCapacidad(error(400, { codigo: 'capacidad_maxima_alcanzada' }))).toBeNull()
    expect(errorDeCapacidad(error(409, { codigo: 'otro' }))).toBeNull()
    expect(errorDeCapacidad(new Error('sin respuesta'))).toBeNull()
    expect(errorDeCapacidad(undefined)).toBeNull()
  })
})
