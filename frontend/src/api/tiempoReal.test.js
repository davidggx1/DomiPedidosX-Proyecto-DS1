import { describe, expect, it } from 'vitest'
import { esperaReconexion, urlSocket } from './tiempoReal.js'

describe('dirección del WebSocket', () => {
  it('cambia http por ws, reemplaza /api y agrega el token', () => {
    expect(urlSocket('/ws/pedidos/mis-entregas/', 'abc', 'http://127.0.0.1:8000/api')).toBe(
      'ws://127.0.0.1:8000/ws/pedidos/mis-entregas/?token=abc',
    )
  })

  it('en https usa wss', () => {
    expect(urlSocket('/ws/x/', 'abc', 'https://domipedidosx.com/api')).toBe('wss://domipedidosx.com/ws/x/?token=abc')
  })

  it('sin sesión no agrega token', () => {
    expect(urlSocket('/ws/x/', undefined, 'http://localhost:8000')).toBe('ws://localhost:8000/ws/x/')
  })
})

describe('espera entre reintentos', () => {
  it('se duplica en cada intento', () => {
    expect([0, 1, 2, 3].map(esperaReconexion)).toEqual([1000, 2000, 4000, 8000])
  })

  it('nunca pasa de 30 segundos', () => {
    expect(esperaReconexion(10)).toBe(30000)
  })
})
