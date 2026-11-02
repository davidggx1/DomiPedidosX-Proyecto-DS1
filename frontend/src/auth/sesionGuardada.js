// Guarda la sesión (token y datos del usuario) en el navegador.
// La usan AuthProvider y el cliente de Axios.
const CLAVE = 'domipedidosx.sesion'

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
