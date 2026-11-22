import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import api from './cliente.js'
import { EVENTO_SESION, consumirAvisoSesionExpirada, leerSesion } from '../auth/sesionGuardada.js'

// Almacenamiento y window de mentira (las pruebas corren en Node)
function almacenamiento() {
  const datos = new Map()
  return {
    getItem: (k) => (datos.has(k) ? datos.get(k) : null),
    setItem: (k, v) => datos.set(k, String(v)),
    removeItem: (k) => datos.delete(k),
  }
}

// Responde según la URL y el token de cada petición; guarda lo que se pidió
function servidor(respuestas) {
  const pedidas = []
  api.defaults.adapter = async (config) => {
    pedidas.push({ url: config.url, auth: config.headers.Authorization })
    const { status, data } = respuestas(config)
    const respuesta = { status, data, headers: {}, config, statusText: '' }
    if (status >= 400) {
      const error = new Error(`HTTP ${status}`)
      error.config = config
      error.response = respuesta
      throw error
    }
    return respuesta
  }
  return pedidas
}

const SESION = { token: 'viejo', refresh: 'r1', usuario: { email: 'a@c.com', rol: 'operador' } }

describe('renovación del token (SCRUM-143)', () => {
  let avisos
  const adaptadorOriginal = api.defaults.adapter

  beforeEach(() => {
    vi.stubGlobal('localStorage', almacenamiento())
    vi.stubGlobal('sessionStorage', almacenamiento())
    const eventos = new EventTarget()
    avisos = 0
    eventos.addEventListener(EVENTO_SESION, () => (avisos += 1))
    vi.stubGlobal('window', eventos)
    localStorage.setItem('domipedidosx.sesion', JSON.stringify(SESION))
  })

  afterEach(() => {
    vi.unstubAllGlobals()
    api.defaults.adapter = adaptadorOriginal
  })

  it('con 401 renueva el token, guarda la sesión y repite la petición', async () => {
    const pedidas = servidor((config) => {
      if (config.url === '/auth/token/refresh/') return { status: 200, data: { access: 'nuevo' } }
      return config.headers.Authorization === 'Bearer nuevo'
        ? { status: 200, data: { ok: true } }
        : { status: 401, data: {} }
    })

    const { data } = await api.get('/pedidos/')

    expect(data).toEqual({ ok: true })
    expect(pedidas.map((p) => p.url)).toEqual(['/pedidos/', '/auth/token/refresh/', '/pedidos/'])
    expect(leerSesion()).toEqual({ ...SESION, token: 'nuevo' })
    expect(avisos).toBe(1)
  })

  it('varias peticiones a la vez comparten una sola renovación', async () => {
    const pedidas = servidor((config) => {
      if (config.url === '/auth/token/refresh/') return { status: 200, data: { access: 'nuevo' } }
      return config.headers.Authorization === 'Bearer nuevo' ? { status: 200, data: {} } : { status: 401, data: {} }
    })

    await Promise.all([api.get('/a/'), api.get('/b/'), api.get('/c/')])

    expect(pedidas.filter((p) => p.url === '/auth/token/refresh/')).toHaveLength(1)
  })

  it('si el refresh también vence, cierra la sesión y avisa al login', async () => {
    servidor(() => ({ status: 401, data: {} }))

    await expect(api.get('/pedidos/')).rejects.toMatchObject({ response: { status: 401 } })

    expect(leerSesion()).toBeNull()
    expect(avisos).toBe(1)
    expect(consumirAvisoSesionExpirada()).toBe(true)
    expect(consumirAvisoSesionExpirada()).toBe(false)
  })

  it('no renueva en el login ni sin refresh token', async () => {
    const pedidas = servidor(() => ({ status: 401, data: {} }))

    await expect(api.post('/usuarios/login/', {}, { sinRenovar: true })).rejects.toBeTruthy()
    localStorage.setItem('domipedidosx.sesion', JSON.stringify({ token: 't', usuario: {} }))
    await expect(api.get('/pedidos/')).rejects.toBeTruthy()

    expect(pedidas.map((p) => p.url)).toEqual(['/usuarios/login/', '/pedidos/'])
    expect(leerSesion()).not.toBeNull()
  })

  it('otros errores no se tocan', async () => {
    const pedidas = servidor(() => ({ status: 500, data: {} }))

    await expect(api.get('/pedidos/')).rejects.toMatchObject({ response: { status: 500 } })
    expect(pedidas).toHaveLength(1)
  })
})
