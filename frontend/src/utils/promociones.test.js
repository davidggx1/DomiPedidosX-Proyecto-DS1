import { describe, expect, it } from 'vitest'
import {
  armarCuerpoPromocion,
  claseEstado,
  contarPorEstado,
  cupoAgotado,
  datosIniciales,
  etiquetaValor,
  fechaLocal,
  filtrarPorEstado,
  formatearFecha,
  mensajeCupoAgotado,
  normalizarValor,
  textoCupo,
  textoPorcentaje,
  textoVigencia,
  validarPromocion,
} from './promociones.js'

const VALIDOS = {
  nombre: 'Martes de combos',
  descripcion: 'Descuento entre semana',
  tipo_descuento: 'porcentaje',
  valor: '15',
  fecha_inicio: '2026-11-15',
  fecha_fin: '2026-11-22',
  condiciones: 'Solo domicilios',
}

describe('validarPromocion', () => {
  it('acepta datos válidos', () => {
    expect(validarPromocion(VALIDOS)).toEqual({})
  })

  it('exige nombre, tipo, valor y fechas', () => {
    const errores = validarPromocion({})
    expect(Object.keys(errores).sort()).toEqual(
      ['fecha_fin', 'fecha_inicio', 'nombre', 'tipo_descuento', 'valor'].sort(),
    )
  })

  it('rechaza un nombre de solo espacios o de más de 100 caracteres', () => {
    expect(validarPromocion({ ...VALIDOS, nombre: '   ' }).nombre).toBeDefined()
    expect(validarPromocion({ ...VALIDOS, nombre: 'a'.repeat(101) }).nombre).toBeDefined()
    expect(validarPromocion({ ...VALIDOS, nombre: 'a'.repeat(100) }).nombre).toBeUndefined()
  })

  it('rechaza una fecha de fin anterior al inicio', () => {
    const errores = validarPromocion({ ...VALIDOS, fecha_fin: '2026-11-14' })
    expect(errores.fecha_fin).toMatch(/anterior/)
  })

  it('una promoción de un solo día es válida', () => {
    expect(validarPromocion({ ...VALIDOS, fecha_fin: '2026-11-15' }).fecha_fin).toBeUndefined()
  })

  it('rechaza un porcentaje mayor que 100 pero acepta exactamente 100', () => {
    expect(validarPromocion({ ...VALIDOS, valor: '100.01' }).valor).toMatch(/mayor que 100/)
    expect(validarPromocion({ ...VALIDOS, valor: '101' }).valor).toBeDefined()
    expect(validarPromocion({ ...VALIDOS, valor: '100' }).valor).toBeUndefined()
  })

  it('rechaza un descuento menor o igual a cero en los dos tipos', () => {
    for (const tipo_descuento of ['porcentaje', 'valor_fijo']) {
      for (const valor of ['0', '-5', '0,00']) {
        expect(validarPromocion({ ...VALIDOS, tipo_descuento, valor }).valor).toBe(
          'El descuento debe ser mayor que 0.',
        )
      }
    }
  })

  it('un valor fijo puede pasar de 100', () => {
    expect(validarPromocion({ ...VALIDOS, tipo_descuento: 'valor_fijo', valor: '12000' })).toEqual({})
  })

  it('acepta coma o punto decimal y limita a 2 decimales', () => {
    expect(validarPromocion({ ...VALIDOS, valor: '12,5' }).valor).toBeUndefined()
    expect(validarPromocion({ ...VALIDOS, valor: '12.5' }).valor).toBeUndefined()
    expect(validarPromocion({ ...VALIDOS, valor: '12.555' }).valor).toMatch(/2 decimales/)
  })

  it('rechaza texto que no es un número y valores demasiado grandes', () => {
    expect(validarPromocion({ ...VALIDOS, valor: 'abc' }).valor).toMatch(/número válido/)
    expect(validarPromocion({ ...VALIDOS, tipo_descuento: 'valor_fijo', valor: '123456789' }).valor).toBeDefined()
  })

  it('rechaza un tipo de descuento desconocido', () => {
    expect(validarPromocion({ ...VALIDOS, tipo_descuento: 'regalo' }).tipo_descuento).toBeDefined()
  })
})

describe('armarCuerpoPromocion', () => {
  it('limpia espacios, normaliza el valor y no envía la sede', () => {
    const cuerpo = armarCuerpoPromocion({ ...VALIDOS, nombre: '  Martes ', valor: ' 12,5 ' })
    expect(cuerpo.nombre).toBe('Martes')
    expect(cuerpo.valor).toBe('12.5')
    expect(cuerpo.sede).toBeUndefined()
  })
})

describe('datosIniciales', () => {
  it('una promoción nueva empieza hoy, en porcentaje', () => {
    const datos = datosIniciales(null, new Date(2026, 10, 15))
    expect(datos).toMatchObject({ nombre: '', tipo_descuento: 'porcentaje', fecha_inicio: '2026-11-15', fecha_fin: '' })
  })

  it('al editar se cargan los valores guardados, sin ceros de más', () => {
    const datos = datosIniciales({ ...VALIDOS, valor: '15.00', descripcion: null, condiciones: null })
    expect(datos.valor).toBe('15')
    expect(datos.descripcion).toBe('')
    expect(datos.condiciones).toBe('')
    expect(datosIniciales({ ...VALIDOS, valor: '12.50' }).valor).toBe('12.5')
  })
})

describe('textos y fechas', () => {
  it('fechaLocal da AAAA-MM-DD con ceros', () => {
    expect(fechaLocal(new Date(2026, 0, 5))).toBe('2026-01-05')
  })

  it('formatea la fecha sin correr el día', () => {
    expect(formatearFecha('2026-11-05')).toBe('05/11/2026')
    expect(formatearFecha('')).toBe('')
    expect(formatearFecha(undefined)).toBe('')
  })

  it('texto de vigencia', () => {
    expect(textoVigencia({ fecha_inicio: '2026-11-15', fecha_fin: '2026-11-22' })).toBe('15/11/2026 – 22/11/2026')
  })

  it('porcentaje sin ceros de más', () => {
    expect(textoPorcentaje('15.00')).toBe('15 %')
    expect(textoPorcentaje('12.50')).toBe('12.5 %')
  })

  it('normalizarValor y la etiqueta según el tipo', () => {
    expect(normalizarValor(' 12,5 ')).toBe('12.5')
    expect(etiquetaValor('porcentaje')).toMatch(/%/)
    expect(etiquetaValor('valor_fijo')).toMatch(/\$/)
  })
})

describe('filtros por estado', () => {
  const lista = [
    { id: 1, estado: 'vigente' },
    { id: 2, estado: 'vigente' },
    { id: 3, estado: 'programada' },
    { id: 4, estado: 'vencida' },
    { id: 5, estado: 'inactiva' },
  ]

  it('cuenta cada estado y el total', () => {
    expect(contarPorEstado(lista)).toEqual({ todas: 5, vigente: 2, programada: 1, vencida: 1, inactiva: 1 })
    expect(contarPorEstado([])).toEqual({ todas: 0, vigente: 0, programada: 0, vencida: 0, inactiva: 0 })
  })

  it('filtra por estado y "todas" devuelve la lista completa', () => {
    expect(filtrarPorEstado(lista, 'todas')).toEqual(lista)
    expect(filtrarPorEstado(lista, 'vigente').map((p) => p.id)).toEqual([1, 2])
    expect(filtrarPorEstado(lista, 'inactiva').map((p) => p.id)).toEqual([5])
  })

  it('cada estado tiene su color', () => {
    expect(claseEstado('vigente')).toContain('exito')
    expect(claseEstado('programada')).toContain('aviso')
    expect(claseEstado('vencida')).toContain('borde')
    expect(claseEstado('inactiva')).toContain('borde')
  })
})

describe('HU-64 · cupo diario', () => {
  const base = {
    nombre: 'Promo', tipo_descuento: 'porcentaje', valor: '10',
    fecha_inicio: '2026-11-15', fecha_fin: '2026-11-20',
  }

  it('el cupo es opcional; vacío se envía como null', () => {
    expect(validarPromocion({ ...base, cupo_max_diario: '' })).toEqual({})
    expect(armarCuerpoPromocion({ ...base, cupo_max_diario: '  ' }).cupo_max_diario).toBeNull()
    expect(armarCuerpoPromocion({ ...base, cupo_max_diario: '50' }).cupo_max_diario).toBe(50)
  })

  it('rechaza cupo 0, negativo, decimal o texto', () => {
    for (const malo of ['0', '-3', '2.5', 'abc']) {
      expect(validarPromocion({ ...base, cupo_max_diario: malo }).cupo_max_diario).toBeTruthy()
    }
  })

  it('muestra el uso del día y avisa si se agotó', () => {
    expect(textoCupo({ cupo_max_diario: null })).toBeNull()
    expect(textoCupo({ cupo_max_diario: 10, usos_hoy: 4, cupo_restante: 6 })).toBe(
      'Hoy: 4 de 10 usos · quedan 6',
    )
    expect(textoCupo({ cupo_max_diario: 10, usos_hoy: 10, cupo_restante: 0 })).toContain('agotado')
    expect(cupoAgotado({ cupo_max_diario: 10, cupo_restante: 0 })).toBe(true)
    expect(cupoAgotado({ cupo_max_diario: null, cupo_restante: null })).toBe(false)
  })

  it('el mensaje al cliente nombra la oferta', () => {
    expect(mensajeCupoAgotado('2x1')).toContain('«2x1»')
  })

  it('al editar carga el cupo actual', () => {
    expect(datosIniciales({ ...base, valor: '10.00', cupo_max_diario: 25 }).cupo_max_diario).toBe('25')
    expect(datosIniciales({ ...base, valor: '10.00', cupo_max_diario: null }).cupo_max_diario).toBe('')
  })
})