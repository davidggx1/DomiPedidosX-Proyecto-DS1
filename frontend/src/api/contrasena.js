import api from './cliente.js'

// HU-05 · Restablecer la contraseña olvidada.

// Responde el mismo mensaje exista o no el correo.
export async function solicitarRestablecimiento(email) {
  const { data } = await api.post('/usuarios/contrasena/solicitar/', { email })
  return data
}

// uid y token vienen en el enlace del correo.
export async function restablecerContrasena({ uid, token, password }) {
  const { data } = await api.post('/usuarios/contrasena/restablecer/', { uid, token, password })
  return data
}
