// Convierte un error de Axios en mensajes listos para mostrar.
// Django REST Framework responde los errores de validación así:
//   { "email": ["Ya existe una cuenta con este correo."], "detail": "..." }
// Devuelve { general, campos } donde campos = { email: "Ya existe..." }.
export function interpretarError(error) {
  if (!error?.response) {
    return {
      general: 'No se pudo conectar con el servidor. Revisa tu conexión e inténtalo de nuevo.',
      campos: {},
    }
  }

  const { status, data } = error.response

  if (status === 401) {
    return { general: 'Tu sesión expiró o no es válida. Inicia sesión de nuevo.', campos: {} }
  }
  if (status === 403) {
    return { general: 'No tienes permiso para realizar esta acción.', campos: {} }
  }
  if (status >= 500) {
    return { general: 'Ocurrió un error en el servidor. Inténtalo más tarde.', campos: {} }
  }

  const campos = {}
  let general = null

  if (data && typeof data === 'object') {
    for (const [clave, valor] of Object.entries(data)) {
      const mensaje = Array.isArray(valor) ? valor.join(' ') : String(valor)
      if (clave === 'detail' || clave === 'non_field_errors') {
        general = mensaje
      } else {
        campos[clave] = mensaje
      }
    }
  }

  if (!general) {
    general = Object.keys(campos).length > 0
      ? 'Revisa los campos marcados.'
      : 'No se pudo completar la solicitud.'
  }

  return { general, campos }
}
