// Guarda la sesión (token y datos del usuario) en el navegador.
// La usan AuthProvider y el cliente de Axios.
const CLAVE = 'domipedidosx.sesion'
const CLAVE_EXPIRADA = 'domipedidosx.sesionExpirada'

// Aviso para AuthProvider cuando el cliente de Axios cambia la sesión por su cuenta
// (renovó el token o la sesión expiró), para que la pantalla se actualice.
export const EVENTO_SESION = 'domipedidosx:sesion'

export function leerSesion() {
  try {
    const texto = localStorage.getItem(CLAVE)
    return texto ? JSON.parse(texto) : null
  } catch {
    // Almacenamiento bloqueado o dato corrupto: se trata como sesión cerrada.
    return null
  }
}

export function guardarSesion(sesion) {
  try {
    if (sesion) {
      localStorage.setItem(CLAVE, JSON.stringify(sesion))
    } else {
      localStorage.removeItem(CLAVE)
    }
  } catch {
    // Sin almacenamiento disponible: la sesión dura mientras la pestaña esté abierta.
  }
}

// Guarda y avisa a AuthProvider (solo para cambios que no vienen de él).
export function guardarSesionYAvisar(sesion, { expirada = false } = {}) {
  guardarSesion(sesion)
  if (expirada) {
    try {
      sessionStorage.setItem(CLAVE_EXPIRADA, '1')
    } catch {
      // Sin almacenamiento: el login no mostrará el aviso, no pasa nada.
    }
  }
  if (typeof window !== 'undefined') window.dispatchEvent(new Event(EVENTO_SESION))
}

// true una sola vez después de que la sesión expiró (para el aviso del login).
export function consumirAvisoSesionExpirada() {
  try {
    const expirada = sessionStorage.getItem(CLAVE_EXPIRADA) === '1'
    sessionStorage.removeItem(CLAVE_EXPIRADA)
    return expirada
  } catch {
    return false
  }
}
