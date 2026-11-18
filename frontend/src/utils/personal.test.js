import { describe, expect, it } from 'vitest'
import {
  armarCuerpoEmpleado,
  cambiosDeAcceso,
  datosInicialesEmpleado,
  etiquetaRol,
  textoSede,
  validarEmpleado,
} from './personal.js'

const EMPLEADO = {
  id: 1, email: 'a@correo.com', nombres: 'Ana', apellidos: 'Mora', tipo_documento: 'CC',
  num_documento: '123', celular: '3001234567', direccion: 'Calle 1', rol: 'OPERADOR',
  sede_id: 2, sede: 'Centro', activa: true,
}

describe('datos y validación', () => {
  it('carga el empleado en el formulario', () => {
    const datos = datosInicialesEmpleado(EMPLEADO)
    expect(datos.rol).toBe('OPERADOR')
    expect(datos.sede_id).toBe('2')
    expect(datosInicialesEmpleado({ ...EMPLEADO, sede_id: null }).sede_id).toBe('')
  })

  it('acepta un empleado correcto', () => {
    expect(validarEmpleado(datosInicialesEmpleado(EMPLEADO))).toEqual({})
  })

  it('exige los campos y un celular de 10 dígitos', () => {
    const errores = validarEmpleado({
      ...datosInicialesEmpleado(EMPLEADO), nombres: ' ', apellidos: '', num_documento: '', celular: '123', direccion: '',
    })
    expect(Object.keys(errores).sort()).toEqual(['apellidos', 'celular', 'direccion', 'nombres', 'num_documento'])
  })

  it('la sede es obligatoria salvo para el administrador', () => {
    const base = datosInicialesEmpleado(EMPLEADO)
    expect(validarEmpleado({ ...base, sede_id: '' }).sede_id).toBeTruthy()
    expect(validarEmpleado({ ...base, rol: 'ADMINISTRADOR', sede_id: '' })).toEqual({})
    expect(validarEmpleado({ ...base, rol: 'OTRO' }).rol).toBeTruthy()
  })
})

describe('cuerpo y cambios de acceso', () => {
  it('arma el cuerpo y quita la sede al administrador', () => {
    const base = datosInicialesEmpleado(EMPLEADO)
    expect(armarCuerpoEmpleado({ ...base, nombres: ' Ana ' })).toMatchObject({ nombres: 'Ana', sede_id: 2 })
    expect(armarCuerpoEmpleado({ ...base, rol: 'ADMINISTRADOR' }).sede_id).toBeNull()
  })

  it('resume lo que cambia en rol y sede', () => {
    const sedes = [{ id: 2, nombre: 'Centro' }, { id: 3, nombre: 'Norte' }]
    const base = datosInicialesEmpleado(EMPLEADO)
    expect(cambiosDeAcceso(EMPLEADO, base, sedes)).toEqual([])
    expect(cambiosDeAcceso(EMPLEADO, { ...base, rol: 'COCINA', sede_id: '3' }, sedes)).toEqual([
      'rol: Operador de sede → Cocina',
      'sede: Centro → Norte',
    ])
    expect(cambiosDeAcceso(EMPLEADO, { ...base, rol: 'ADMINISTRADOR' }, sedes)).toContain('sede: Centro → ninguna')
  })

  it('etiquetas y sede del listado', () => {
    expect(etiquetaRol('cocina')).toBe('Cocina')
    expect(etiquetaRol('')).toBe('Sin rol')
    expect(textoSede({ sede: 'Centro' })).toBe('Centro')
    expect(textoSede({ sede: 'N/A' })).toBeNull()
    expect(textoSede({ sede: { nombre: 'Norte' } })).toBe('Norte')
  })
})