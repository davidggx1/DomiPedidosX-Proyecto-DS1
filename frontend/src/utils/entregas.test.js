import { describe, expect, it } from 'vitest'
import {
  avanceDeEntrega,
  avisoDePago,
  calcularCambio,
  destinoEntrega,
  enlaceMapa,
  enlaceRuta,
  mensajeErrorGps,
} from './entregas.js'

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

describe('avance de la entrega', () => {
  it('sigue el orden recogido, en camino, entregado', () => {
    expect(avanceDeEntrega({ estado: 'listo_despacho', siguientes_estados: ['recogido'] }).estado).toBe('recogido')
    expect(avanceDeEntrega({ estado: 'recogido', siguientes_estados: ['en_camino'] }).estado).toBe('en_camino')
    expect(avanceDeEntrega({ estado: 'en_camino', siguientes_estados: ['entregado'] }).estado).toBe('entregado')
  })

  it('sin permiso de la API o ya entregado no hay botón', () => {
    expect(avanceDeEntrega({ estado: 'recogido', siguientes_estados: [] })).toBeNull()
    expect(avanceDeEntrega({ estado: 'entregado', siguientes_estados: [] })).toBeNull()
  })
})

describe('cambio para el cliente', () => {
  it('resta el total del monto recibido', () => {
    expect(calcularCambio('50000', '35000.00')).toBe(15000)
    expect(calcularCambio('35000', '35000.00')).toBe(0)
  })

  it('sin monto o si no alcanza no hay cambio', () => {
    expect(calcularCambio('', '35000.00')).toBeNull()
    expect(calcularCambio('20000', '35000.00')).toBeNull()
  })
})

describe('ruta hasta el cliente (HU-44)', () => {
  const conCoordenadas = { entrega_latitud: 3.4372, entrega_longitud: -76.5447 }

  it('el destino son las coordenadas cuando existen', () => {
    expect(destinoEntrega(conCoordenadas)).toBe('3.4372,-76.5447')
  })

  it('sin coordenadas el destino es la dirección escrita', () => {
    expect(destinoEntrega({ direccion_completa: 'Carrera 10 # 20-30, San Fernando, Cali' })).toBe(
      'Carrera 10 # 20-30, San Fernando, Cali',
    )
  })

  it('con GPS traza la ruta desde la posición del repartidor', () => {
    const url = new URL(enlaceRuta(conCoordenadas, { latitud: 3.45, longitud: -76.53 }))
    expect(url.origin + url.pathname).toBe('https://www.google.com/maps/dir/')
    expect(url.searchParams.get('origin')).toBe('3.45,-76.53')
    expect(url.searchParams.get('destination')).toBe('3.4372,-76.5447')
  })

  it('sin GPS deja que Google Maps use la ubicación del celular', () => {
    expect(new URL(enlaceRuta(conCoordenadas)).searchParams.has('origin')).toBe(false)
  })

  it('explica cada falla del GPS', () => {
    expect(mensajeErrorGps(1)).toMatch(/permiso/)
    expect(mensajeErrorGps(2)).toMatch(/dirección escrita/)
    expect(mensajeErrorGps(3)).toMatch(/tardando/)
  })
})
