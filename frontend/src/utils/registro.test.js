import { describe, expect, it } from 'vitest'
import { armarCuerpoRegistro, fechaHoy, soloDigitos, validarRegistro } from './registro.js'

const HOY = new Date(2026, 10, 12) // 12 de noviembre de 2026

const VALIDOS = {
  email: 'ana@correo.com',
  password: 'ClaveSegura2026',
  confirmarPassword: 'ClaveSegura2026',
  tipo_documento: 'CC',
  num_documento: '1234567890',
  nombres: 'Ana',
  apellidos: 'Prueba',
  celular: '3001234567',
  fecha_nacimiento: '2000-05-20',
}

describe('validarRegistro', () => {
  it('acepta datos válidos', () => {
    expect(validarRegistro(VALIDOS, HOY)).toEqual({})
  })

  it('exige todos los campos', () => {
    const errores = validarRegistro({}, HOY)
    expect(Object.keys(errores).sort()).toEqual(
      [
        'apellidos',
        'celular',
        'confirmarPassword',
        'email',
        'fecha_nacimiento',
        'nombres',
        'num_documento',
        'password',
        'tipo_documento',
      ].sort(),
    )
  })

  it('rechaza un correo mal formado', () => {
    expect(validarRegistro({ ...VALIDOS, email: 'abc' }, HOY).email).toBeDefined()
    expect(validarRegistro({ ...VALIDOS, email: 'a@b' }, HOY).email).toBeDefined()
  })

  it('rechaza una contraseña corta', () => {
    const errores = validarRegistro({ ...VALIDOS, password: '123', confirmarPassword: '123' }, HOY)
    expect(errores.password).toMatch(/al menos 8/)
  })

  it('rechaza si las contraseñas no coinciden', () => {
    const errores = validarRegistro({ ...VALIDOS, confirmarPassword: 'Otra12345' }, HOY)
    expect(errores.confirmarPassword).toBeDefined()
  })

  it('HU-02: el celular debe tener exactamente 10 dígitos', () => {
    expect(validarRegistro({ ...VALIDOS, celular: '300123456' }, HOY).celular).toBeDefined()
    expect(validarRegistro({ ...VALIDOS, celular: '30012345678' }, HOY).celular).toBeDefined()
    expect(validarRegistro({ ...VALIDOS, celular: '300123456a' }, HOY).celular).toBeDefined()
    expect(validarRegistro({ ...VALIDOS, celular: '3001234567' }, HOY).celular).toBeUndefined()
  })

  it('rechaza un tipo de documento desconocido', () => {
    expect(validarRegistro({ ...VALIDOS, tipo_documento: 'XX' }, HOY).tipo_documento).toBeDefined()
  })

  it('rechaza un documento de más de 12 caracteres', () => {
    const errores = validarRegistro({ ...VALIDOS, num_documento: '1234567890123' }, HOY)
    expect(errores.num_documento).toBeDefined()
  })

  it('rechaza nombres vacíos o solo con espacios', () => {
    expect(validarRegistro({ ...VALIDOS, nombres: '   ' }, HOY).nombres).toBeDefined()
  })

  it('rechaza una fecha de nacimiento futura', () => {
    expect(validarRegistro({ ...VALIDOS, fecha_nacimiento: '2026-11-13' }, HOY).fecha_nacimiento).toBeDefined()
    expect(validarRegistro({ ...VALIDOS, fecha_nacimiento: '2026-11-12' }, HOY).fecha_nacimiento).toBeUndefined()
  })
})

describe('armarCuerpoRegistro', () => {
  it('no envía la confirmación y limpia espacios y mayúsculas del correo', () => {
    const cuerpo = armarCuerpoRegistro({ ...VALIDOS, email: '  Ana@Correo.com ', nombres: ' Ana ' })
    expect(cuerpo.confirmarPassword).toBeUndefined()
    expect(cuerpo.email).toBe('ana@correo.com')
    expect(cuerpo.nombres).toBe('Ana')
  })
})

describe('utilidades', () => {
  it('soloDigitos quita todo lo que no es número', () => {
    expect(soloDigitos('300 123-45a67')).toBe('3001234567')
  })

  it('fechaHoy da AAAA-MM-DD con ceros', () => {
    expect(fechaHoy(new Date(2026, 0, 5))).toBe('2026-01-05')
  })
})