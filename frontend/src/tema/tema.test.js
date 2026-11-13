import { describe, expect, it } from 'vitest'
import { TEMAS, esTemaValido, resolverTema, temaContrario } from './tema.js'

describe('tema claro u oscuro', () => {
  it('usa el tema que la persona eligió, sin importar su sistema', () => {
    expect(resolverTema('claro', true)).toBe(TEMAS.CLARO)
    expect(resolverTema('oscuro', false)).toBe(TEMAS.OSCURO)
  })

  it('si nunca eligió, sigue la preferencia del sistema', () => {
    expect(resolverTema(null, true)).toBe(TEMAS.OSCURO)
    expect(resolverTema(null, false)).toBe(TEMAS.CLARO)
  })

  it('ignora valores guardados que no son un tema', () => {
    expect(resolverTema('azul', false)).toBe(TEMAS.CLARO)
    expect(esTemaValido('')).toBe(false)
  })

  it('el botón alterna entre los dos temas', () => {
    expect(temaContrario(TEMAS.CLARO)).toBe(TEMAS.OSCURO)
    expect(temaContrario(TEMAS.OSCURO)).toBe(TEMAS.CLARO)
  })
})
