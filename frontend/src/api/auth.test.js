import { beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('./cliente.js', () => ({ default: { post: vi.fn(), get: vi.fn() } }))

const { default: api } = await import('./cliente.js')
const {
  ErrorInicioSesion,
  MENSAJE_CREDENCIALES,
  MENSAJE_DEMASIADOS_INTENTOS,
  autenticar,
  esCredencialInvalida,
  noEsPersonal,
  nombreDelCliente,
} = await import('./auth.js')

const error401 = (detail = 'Credenciales inválidas.', code = 'no_active_account') => ({
  response: { status: 401, data: { detail, code } },
})
// Contraseña correcta, pero la cuenta no es de personal: el backend pide probar como cliente
const noPersonal = () => error401('Credenciales inválidas.', 'no_es_personal')
const error429 = (detail) => ({ response: { status: 429, data: detail ? { detail } : {} } })

describe('inicio de sesión real (HU-03 y HU-04)', () => {
  beforeEach(() => vi.resetAllMocks())

  it('el personal entra con su rol y su sede', async () => {
    api.post.mockResolvedValueOnce({ data: { access: 'a', refresh: 'r', rol: 'operador', sede_id: 2 } })

    const sesion = await autenticar('  op@correo.com ', 'clave')

    expect(api.post).toHaveBeenCalledWith(
      '/usuarios/login-personal/',
      { email: 'op@correo.com', password: 'clave' },
      { sinRenovar: true },
    )
    expect(sesion).toEqual({
      token: 'a',
      refresh: 'r',
      usuario: { nombre: 'op@correo.com', email: 'op@correo.com', rol: 'operador', sede: 2 },
    })
  })

  it('si no es personal, entra como cliente con su nombre', async () => {
    api.post
      .mockRejectedValueOnce(noPersonal())
      .mockResolvedValueOnce({ data: { access: 'a2', refresh: 'r2' } })
    api.get.mockResolvedValueOnce({ data: { nombres: 'Ana', apellidos: 'Gómez' } })

    const sesion = await autenticar('ana@correo.com', 'clave')

    expect(api.post).toHaveBeenLastCalledWith(
      '/usuarios/login/',
      { email: 'ana@correo.com', password: 'clave' },
      { sinRenovar: true },
    )
    expect(api.get).toHaveBeenCalledWith('/usuarios/perfil/', {
      sinRenovar: true,
      headers: { Authorization: 'Bearer a2' },
    })
    expect(sesion.usuario).toEqual({ nombre: 'Ana Gómez', email: 'ana@correo.com', rol: 'cliente', sede: null })
    expect(sesion.refresh).toBe('r2')
  })

  it('contraseña mala: mensaje claro sin probar el login de cliente', async () => {
    api.post.mockRejectedValue(error401())

    await expect(autenticar('x@correo.com', 'mala')).rejects.toThrow(MENSAJE_CREDENCIALES)
    // Una sola petición: el intento cuenta una vez en el límite del backend
    expect(api.post).toHaveBeenCalledTimes(1)
  })

  it('cliente con contraseña mala: mensaje claro', async () => {
    api.post.mockRejectedValueOnce(noPersonal()).mockRejectedValueOnce(error401())

    await expect(autenticar('ana@correo.com', 'mala')).rejects.toThrow(MENSAJE_CREDENCIALES)
  })

  it('demasiados intentos (429): muestra el mensaje del backend', async () => {
    api.post.mockRejectedValueOnce(error429(`${MENSAJE_DEMASIADOS_INTENTOS} Podrás intentarlo en 60 segundos.`))

    const fallo = await autenticar('x@correo.com', 'clave').catch((e) => e)
    expect(fallo).toBeInstanceOf(ErrorInicioSesion)
    expect(fallo.message).toMatch(/Podrás intentarlo en 60 segundos/)
    expect(api.post).toHaveBeenCalledTimes(1)
  })

  it('429 en el login de cliente o sin detalle: mensaje por defecto', async () => {
    api.post.mockRejectedValueOnce(noPersonal()).mockRejectedValueOnce(error429())

    await expect(autenticar('ana@correo.com', 'clave')).rejects.toThrow(MENSAJE_DEMASIADOS_INTENTOS)
  })

  it('cuenta inactiva: avisa sin probar el login de cliente', async () => {
    api.post.mockRejectedValueOnce(error401('La cuenta está inactiva.'))

    await expect(autenticar('x@correo.com', 'clave')).rejects.toThrow(/inactiva/)
    expect(api.post).toHaveBeenCalledTimes(1)
  })

  it('personal sin sede (perfil de cliente 403): credenciales incorrectas', async () => {
    api.post
      .mockRejectedValueOnce(noPersonal())
      .mockResolvedValueOnce({ data: { access: 'a', refresh: 'r' } })
    api.get.mockRejectedValueOnce({ response: { status: 403, data: {} } })

    const fallo = await autenticar('x@correo.com', 'clave').catch((e) => e)
    expect(fallo).toBeInstanceOf(ErrorInicioSesion)
    expect(fallo.message).toBe(MENSAJE_CREDENCIALES)
  })

  it('sin conexión: deja pasar el error original', async () => {
    const sinRed = { message: 'Network Error' }
    api.post.mockRejectedValueOnce(sinRed)

    await expect(autenticar('x@correo.com', 'clave')).rejects.toBe(sinRed)
  })

  it('utilidades', () => {
    expect(esCredencialInvalida(error401())).toBe(true)
    expect(esCredencialInvalida(error401('La cuenta está inactiva.'))).toBe(false)
    expect(esCredencialInvalida({ response: { status: 500 } })).toBe(false)
    expect(noEsPersonal(noPersonal())).toBe(true)
    expect(noEsPersonal(error401())).toBe(false)
    expect(nombreDelCliente({ nombres: 'Ana', apellidos: '' }, 'a@c.com')).toBe('Ana')
    expect(nombreDelCliente({}, 'a@c.com')).toBe('a@c.com')
  })
})
