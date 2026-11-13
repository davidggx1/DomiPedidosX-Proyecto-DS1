import { describe, expect, it } from 'vitest'
import { autorDelPaso, textoRango, totalPaginas } from './historial.js'

describe('historial de pedidos (HU-66)', () => {
  it('calcula cuántas páginas hay', () => {
    expect(totalPaginas(0)).toBe(1)
    expect(totalPaginas(20)).toBe(1)
    expect(totalPaginas(21)).toBe(2)
  })

  it('describe qué pedidos se están mostrando', () => {
    expect(textoRango(1, 25)).toBe('Mostrando 1–20 de 25 pedidos')
    expect(textoRango(2, 25)).toBe('Mostrando 21–25 de 25 pedidos')
    expect(textoRango(1, 1)).toBe('Mostrando 1–1 de 1 pedido')
    expect(textoRango(1, 0)).toBe('Sin pedidos')
  })

  it('los cambios automáticos aparecen como hechos por el sistema', () => {
    expect(autorDelPaso({ usuario: 'operador@correo.com' })).toBe('operador@correo.com')
    expect(autorDelPaso({ usuario: null })).toBe('Sistema')
  })
})
