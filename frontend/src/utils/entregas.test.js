import { describe, expect, it } from 'vitest'
import { avisoDePago, enlaceMapa } from './entregas.js'

const base = { total: '35000.00', metodo_pago: 'efectivo', metodo_pago_nombre: 'Efectivo' }

describe('aviso de pago de la entrega', () => {
  it('en efectivo pendiente resalta cuánto cobrar', () => {
    const aviso = avisoDePago({ ...base, cobrar_en_efectivo: true })
    expect(aviso.tipo).toBe('aviso')
    expect(aviso.titulo).toMatch(/^Cobrar .*35\.000 en efectivo$/)
  })

  it('con tarjeta o transferencia avisa que ya está pagado', () => {
    const tarjeta = { ...base, metodo_pago: 'tarjeta', metodo_pago_nombre: 'Tarjeta', cobrar_en_efectivo: false }
    expect(avisoDePago(tarjeta)).toMatchObject({ tipo: 'exito', titulo: 'Pagado con tarjeta' })
  })

  it('en efectivo ya pagado no pide cobrar', () => {
    expect(avisoDePago({ ...base, cobrar_en_efectivo: false })).toMatchObject({
      tipo: 'exito',
      titulo: 'Pagado con efectivo',
    })
  })

  it('sin factura pide confirmar con el operador', () => {
    expect(avisoDePago({ total: null, metodo_pago: null, cobrar_en_efectivo: false }).tipo).toBe('info')
  })
})

describe('enlace al mapa', () => {
  it('usa las coordenadas cuando las hay', () => {
    expect(enlaceMapa({ entrega_latitud: 3.4372, entrega_longitud: -76.5447 })).toBe(
      'https://www.google.com/maps/search/?api=1&query=3.4372%2C-76.5447',
    )
  })

  it('sin coordenadas busca la dirección y el barrio', () => {
    const enlace = enlaceMapa({ entrega_direccion: 'Carrera 10 # 20-30', entrega_barrio: 'San Fernando' })
    expect(decodeURIComponent(enlace)).toContain('query=Carrera 10 # 20-30, San Fernando, Cali')
  })
})
