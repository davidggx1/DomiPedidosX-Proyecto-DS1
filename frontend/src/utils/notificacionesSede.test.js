import { describe, expect, it } from 'vitest'
import { agruparPorEvento, resumenDestinatarios, validarCorreoNuevo } from './notificacionesSede.js'

const lista = [
  { id: 1, evento: 'stock_bajo', rol: 'operador', correo: '' },
  { id: 2, evento: 'stock_bajo', rol: '', correo: 'zeta@correo.com' },
  { id: 3, evento: 'stock_bajo', rol: '', correo: 'ana@correo.com' },
  { id: 4, evento: 'sobrecupo', rol: 'cocina', correo: '' },
  { id: 5, evento: 'otro', rol: 'cocina', correo: '' },
]

describe('notificaciones de la sede (HU-83)', () => {
  it('agrupa por evento, separa roles y correos y ordena los correos', () => {
    const grupos = agruparPorEvento(lista)
    expect(Object.keys(grupos)).toEqual(['stock_bajo', 'cancelacion', 'sobrecupo'])
    expect(grupos.stock_bajo.roles.operador.id).toBe(1)
    expect(grupos.stock_bajo.correos.map((s) => s.correo)).toEqual(['ana@correo.com', 'zeta@correo.com'])
    expect(grupos.cancelacion).toEqual({ roles: {}, correos: [] })
    expect(grupos.sobrecupo.roles.cocina.id).toBe(4)
  })

  it('valida el correo nuevo', () => {
    const actuales = [{ correo: 'ana@correo.com' }]
    expect(validarCorreoNuevo('  ', actuales)).toBe('Escribe un correo.')
    expect(validarCorreoNuevo('ana', actuales)).toMatch(/correo válido/)
    expect(validarCorreoNuevo(' ANA@correo.com ', actuales)).toBe('Ese correo ya recibe este aviso.')
    expect(validarCorreoNuevo('gerente@correo.com', actuales)).toBeNull()
  })

  it('resume quién recibe el aviso', () => {
    const grupos = agruparPorEvento(lista)
    expect(resumenDestinatarios(grupos.cancelacion)).toBe('Nadie recibe este aviso por correo')
    expect(resumenDestinatarios(grupos.sobrecupo)).toBe('Lo reciben: Cocina')
    expect(resumenDestinatarios(grupos.stock_bajo)).toBe('Lo reciben: Operadores y 2 correos')
    const unCorreo = { roles: { administrador: {}, cocina: {} }, correos: [{}] }
    expect(resumenDestinatarios(unCorreo)).toBe('Lo reciben: Administradores, Cocina y 1 correo')
  })
})
