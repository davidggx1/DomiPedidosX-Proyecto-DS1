import { describe, expect, it } from 'vitest'
import {
  capacidadDeEvento,
  describirCapacidad,
  errorDeCapacidad,
  interpretarCapacidad,
  umbralSugerido,
} from './capacidad.js'

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

describe('alerta de capacidad cercana al tope (HU-60)', () => {
  const franja = { estado: 'disponible', activos: 16, maximo: 20, porcentaje: 80, umbral_alerta: 16, en_alerta: true }

  it('muestra la ocupación contra el límite', () => {
    expect(describirCapacidad(franja).texto).toBe('16 de 20 pedidos ocupados')
  })

  it('al llegar al umbral es una alerta (amarilla)', () => {
    const r = describirCapacidad(franja)
    expect(r.nivel).toBe('alerta')
    expect(r.titulo).toBe('Capacidad cercana al tope')
    expect(r.porcentaje).toBe(80)
  })

  it('por debajo del umbral es normal y la alerta se apaga', () => {
    const r = describirCapacidad({ ...franja, activos: 15, porcentaje: 75, en_alerta: false })
    expect(r.nivel).toBe('normal')
    expect(r.texto).toBe('15 de 20 pedidos ocupados')
  })

  it('al 100% es saturada', () => {
    const r = describirCapacidad({ ...franja, estado: 'saturada', activos: 20, porcentaje: 100 })
    expect(r.nivel).toBe('saturada')
    expect(r.texto).toBe('20 de 20 pedidos ocupados')
  })

  it('sin franja no hay barra ni cifras', () => {
    const r = describirCapacidad({ estado: 'sin_franja', activos: 3, maximo: null, porcentaje: null })
    expect(r.nivel).toBe('sin_franja')
    expect(r.porcentaje).toBeNull()
  })

  it('sin datos no muestra nada', () => {
    expect(describirCapacidad(null)).toBeNull()
  })

  it('solo toma el estado de los eventos de capacidad', () => {
    expect(capacidadDeEvento({ tipo: 'capacidad_actualizada', capacidad: franja })).toBe(franja)
    expect(capacidadDeEvento({ tipo: 'pedido_nuevo', pedido: {} })).toBeNull()
    expect(capacidadDeEvento({ tipo: 'capacidad_actualizada' })).toBeNull()
    expect(capacidadDeEvento(undefined)).toBeNull()
  })

  it('el umbral sugerido es el 80% del máximo, redondeado hacia arriba', () => {
    expect(umbralSugerido(10)).toBe(8)
    expect(umbralSugerido(20)).toBe(16)
    expect(umbralSugerido(5)).toBe(4)
    expect(umbralSugerido(7)).toBe(6)
    expect(umbralSugerido(15)).toBe(12)
    expect(umbralSugerido(1)).toBe(1)
  })

  it('el umbral sugerido nunca pasa del máximo ni baja de 1', () => {
    for (let maximo = 1; maximo <= 200; maximo += 1) {
      const umbral = umbralSugerido(maximo)
      expect(umbral).toBeGreaterThanOrEqual(1)
      expect(umbral).toBeLessThanOrEqual(maximo)
    }
    expect(umbralSugerido('')).toBe(1)
    expect(umbralSugerido(0)).toBe(1)
  })
})
