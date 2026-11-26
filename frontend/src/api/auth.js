import api from './cliente.js'
import { ROLES } from '../auth/roles.js'

// Inicio de sesión real (HU-03 clientes y HU-04 personal).
// Un solo formulario para todos: primero se prueba como personal, que devuelve el rol
// y la sede; si la contraseña es correcta pero la cuenta no es de personal
// (code "no_es_personal"), se prueba como cliente.
// Con una contraseña mala no se hace la segunda petición: cada intento cuenta una
// sola vez en el límite contra fuerza bruta del backend (docs/seguridad.md).

export const MENSAJE_CREDENCIALES = 'Correo o contraseña incorrectos.'
export const MENSAJE_DEMASIADOS_INTENTOS = 'Demasiados intentos. Espera unos minutos e inténtalo de nuevo.'
const MENSAJE_INACTIVA = 'La cuenta está inactiva.'

export class ErrorInicioSesion extends Error {}

// 401 por credenciales (no por cuenta inactiva): vale la pena probar el otro login.
export function esCredencialInvalida(error) {
  return error.response?.status === 401 && error.response.data?.detail !== MENSAJE_INACTIVA
}

// Credenciales correctas, pero no es personal (un cliente): vale la pena probar el login de cliente.
export function noEsPersonal(error) {
  return error.response?.status === 401 && error.response.data?.code === 'no_es_personal'
}

export function nombreDelCliente(perfil, email) {
  return [perfil?.nombres, perfil?.apellidos].filter(Boolean).join(' ').trim() || email
}

function errorLegible(error) {
  // 429: el backend frenó el login por demasiados intentos (por IP o por cuenta)
  if (error.response?.status === 429) {
    return new ErrorInicioSesion(error.response.data?.detail || MENSAJE_DEMASIADOS_INTENTOS)
  }
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
    if (!noEsPersonal(error)) throw errorLegible(error)
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
