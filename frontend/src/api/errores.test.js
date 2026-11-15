import { describe, expect, it } from 'vitest'
import { mensajesSinCampos } from './errores.js'

describe('mensajes de error sin nombres de campos', () => {
  it('quita el nombre del campo', () => {
    expect(mensajesSinCampos({ direccion_id: ['La dirección está fuera de la cobertura de esta sede.'] })).toBe(
      'La dirección está fuera de la cobertura de esta sede.',
    )
  })

  it('pone detail primero y omite el código interno', () => {
    expect(mensajesSinCampos({ codigo: 'x', metodo_pago: 'Elige un método.', detail: 'No se pudo.' })).toBe(
      'No se pudo. Elige un método.',
    )
  })

  it('aplana listas y objetos anidados', () => {
    expect(mensajesSinCampos({ tamano_id: ['Debes elegir un tamaño.'], adiciones: { 0: ['Agotada.'] } })).toBe(
      'Debes elegir un tamaño. Agotada.',
    )
  })

  it('acepta texto o vacío', () => {
    expect(mensajesSinCampos('Error')).toBe('Error')
    expect(mensajesSinCampos(null)).toBe('')
  })
})
