import { describe, expect, it } from 'vitest'
import { validarPerfil } from './perfil.js'

const valido = { nombres: 'Laura', apellidos: 'Gómez', celular: '3101112233' }

describe('validación del perfil', () => {
  it('un perfil completo no tiene errores', () => {
    expect(validarPerfil(valido)).toEqual({})
  })

  it('nombres y apellidos son obligatorios', () => {
    const errores = validarPerfil({ ...valido, nombres: '  ', apellidos: '' })
    expect(Object.keys(errores)).toEqual(['nombres', 'apellidos'])
  })

  it('el celular debe tener 10 dígitos numéricos', () => {
    for (const celular of ['310111223', '31011122334', '310-111-223', 'abcdefghij']) {
      expect(validarPerfil({ ...valido, celular }).celular).toBeDefined()
    }
  })
})
