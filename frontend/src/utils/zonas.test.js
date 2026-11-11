import { describe, expect, it } from 'vitest'
import {
  formatearTarifa,
  formatearTiempo,
  formularioConfigurado,
  validarTarifaTiempo,
  zonaConfigurada,
} from './zonas.js'

describe('validarTarifaTiempo', () => {
  it('acepta tarifa 0 y tiempo mayor que 0', () => {
    expect(validarTarifaTiempo({ tarifa_domicilio: '0', tiempo_estimado: '1', activo: true })).toEqual({})
    expect(validarTarifaTiempo({ tarifa_domicilio: '3000.50', tiempo_estimado: 40, activo: true })).toEqual({})
  })

  it('rechaza letras, negativos y notación científica en la tarifa', () => {
    for (const tarifa of ['abc', '12abc', '-1', '1e3']) {
      const errores = validarTarifaTiempo({ tarifa_domicilio: tarifa, tiempo_estimado: '40', activo: false })
      expect(errores.tarifa_domicilio).toBeTruthy()
    }
  })

  it('rechaza tiempo 0, negativo, decimal o con letras', () => {
    for (const tiempo of ['0', '-5', '1.5', 'abc']) {
      const errores = validarTarifaTiempo({ tarifa_domicilio: '3000', tiempo_estimado: tiempo, activo: false })
      expect(errores.tiempo_estimado).toBeTruthy()
    }
  })

  it('exige tarifa y tiempo solo si la zona queda activa', () => {
    const activa = validarTarifaTiempo({ tarifa_domicilio: '', tiempo_estimado: '', activo: true })
    expect(Object.keys(activa)).toEqual(['tarifa_domicilio', 'tiempo_estimado'])
    expect(validarTarifaTiempo({ tarifa_domicilio: '', tiempo_estimado: '', activo: false })).toEqual({})
  })
})

describe('configuración de la zona', () => {
  it('formularioConfigurado necesita ambos valores', () => {
    expect(formularioConfigurado({ tarifa_domicilio: '0', tiempo_estimado: '30' })).toBe(true)
    expect(formularioConfigurado({ tarifa_domicilio: '', tiempo_estimado: '30' })).toBe(false)
    expect(formularioConfigurado({ tarifa_domicilio: '0', tiempo_estimado: '' })).toBe(false)
  })

  it('zonaConfigurada trata la tarifa 0 como configurada', () => {
    expect(zonaConfigurada({ tarifa_domicilio: '0.00', tiempo_estimado: 30 })).toBe(true)
    expect(zonaConfigurada({ tarifa_domicilio: null, tiempo_estimado: 30 })).toBe(false)
    expect(zonaConfigurada({ tarifa_domicilio: '3000.00', tiempo_estimado: null })).toBe(false)
  })

  it('formatea los valores faltantes', () => {
    expect(formatearTarifa(null)).toBe('Sin tarifa')
    expect(formatearTiempo(null)).toBe('Sin tiempo')
    expect(formatearTarifa(12000)).toBe('$12.000')
    expect(formatearTiempo(40)).toBe('40 min')
  })
})