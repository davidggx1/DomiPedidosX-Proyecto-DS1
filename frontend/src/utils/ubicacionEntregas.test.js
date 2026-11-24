import { describe, expect, it } from 'vitest'
import { llevaPedido, puntosDelMapa, textoUbicacion } from './ubicacionEntregas.js'

const AHORA = Date.parse('2026-11-24T20:00:00Z')

describe('ubicación de los repartidores (HU-38)', () => {
  it('solo se comparte con un pedido recogido o en camino', () => {
    expect(llevaPedido([{ estado: 'listo_despacho' }])).toBe(false)
    expect(llevaPedido([{ estado: 'listo_despacho' }, { estado: 'en_camino' }])).toBe(true)
    expect(llevaPedido([{ estado: 'recogido' }])).toBe(true)
    expect(llevaPedido(null)).toBe(false)
  })

  it('texto de la última ubicación', () => {
    expect(textoUbicacion({ ubicacion_actualizada_en: null }, AHORA)).toBe('Aún sin ubicación del repartidor')
    expect(textoUbicacion({ ubicacion_actualizada_en: '2026-11-24T19:59:35Z', sin_senal: false }, AHORA)).toBe(
      'Ubicación de hace 25 s',
    )
    expect(textoUbicacion({ ubicacion_actualizada_en: '2026-11-24T19:56:30Z', sin_senal: true }, AHORA)).toBe(
      'Sin señal desde hace 3 min',
    )
  })

  it('puntos a encuadrar, sin los que faltan', () => {
    const datos = {
      sede: { ubicacion: { latitud: 3.45, longitud: -76.53 } },
      entregas: [
        { ubicacion: { latitud: 3.44, longitud: -76.54 }, destino: { latitud: 3.43, longitud: -76.55 } },
        { ubicacion: null, destino: null },
      ],
    }
    expect(puntosDelMapa(datos)).toEqual([
      [3.45, -76.53],
      [3.44, -76.54],
      [3.43, -76.55],
    ])
    expect(puntosDelMapa(null)).toEqual([])
  })
})
