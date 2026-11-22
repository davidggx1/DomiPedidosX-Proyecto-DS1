import api from './cliente.js'
import { ROLES } from '../auth/roles.js'

// Inicio de sesión real (HU-03 clientes y HU-04 personal).
// Un solo formulario para todos: primero se prueba como personal, que devuelve el rol
// y la sede; si esas credenciales no son de personal, se prueba como cliente.

export const MENSAJE_CREDENCIALES = 'Correo o contraseña incorrectos.'
const MENSAJE_INACTIVA = 'La cuenta está inactiva.'

export class ErrorInicioSesion extends Error {}

// 401 por credenciales (no por cuenta inactiva): vale la pena probar el otro login.
export function esCredencialInvalida(error) {
  return error.response?.status === 401 && error.response.data?.detail !== MENSAJE_INACTIVA
}

export function nombreDelCliente(perfil, email) {
  return [perfil?.nombres, perfil?.apellidos].filter(Boolean).join(' ').trim() || email
}

function errorLegible(error) {
  if (error.response?.data?.detail === MENSAJE_INACTIVA) {
    return new ErrorInicioSesion('Tu cuenta está inactiva. Comunícate con el administrador.')
  }
  if (esCredencialInvalida(error)) return new ErrorInicioSesion(MENSAJE_CREDENCIALES)
  return error // red, servidor caído...: el formulario lo muestra con interpretarError
}

// Devuelve la sesión lista para AuthProvider: { token, refresh, usuario }.
export async function autenticar(email, password) {
  const credenciales = { email: email.trim(), password }
  const opciones = { sinRenovar: true }

  try {
    const { data } = await api.post('/usuarios/login-personal/', credenciales, opciones)
    return {
      token: data.access,
      refresh: data.refresh,
      usuario: { nombre: credenciales.email, email: credenciales.email, rol: data.rol, sede: data.sede_id },
    }
  } catch (error) {
    if (!esCredencialInvalida(error)) throw errorLegible(error)
  }

  try {
    const { data } = await api.post('/usuarios/login/', credenciales, opciones)
    // Confirma que es un cliente y trae su nombre para el encabezado
    const { data: perfil } = await api.get('/usuarios/perfil/', {
      ...opciones,
      headers: { Authorization: `Bearer ${data.access}` },
    })
    return {
      token: data.access,
      refresh: data.refresh,
      usuario: {
        nombre: nombreDelCliente(perfil, credenciales.email),
        email: credenciales.email,
        rol: ROLES.CLIENTE,
        sede: null,
      },
    }
  } catch (error) {
    // 403 en el perfil: cuenta válida pero ni cliente ni personal con sede
    if (error.response?.status === 403) throw new ErrorInicioSesion(MENSAJE_CREDENCIALES)
    throw errorLegible(error)
  }
}
