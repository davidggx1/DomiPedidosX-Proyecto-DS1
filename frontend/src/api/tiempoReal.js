import { leerSesion } from '../auth/sesionGuardada.js'
import api from './cliente.js'

// The server closes with these codes when there is no session or no permission:
// trying again would fail the same way
const SIN_PERMISO = [4401, 4403]
const ESPERA_MAXIMA_MS = 30000

// 1 s, 2 s, 4 s... up to 30 s between attempts, so a fallen server is not flooded
export function esperaReconexion(intento) {
  return Math.min(1000 * 2 ** intento, ESPERA_MAXIMA_MS)
}

// ws:// address of the backend, on the same server Axios talks to. The browser cannot
// send headers on a WebSocket, so the token travels in ?token= (pedidos/middleware.py)
export function urlSocket(ruta, token, base = api.defaults.baseURL) {
  const url = new URL(base)
  url.protocol = url.protocol === 'https:' ? 'wss:' : 'ws:'
  url.pathname = ruta
  url.search = token ? `?token=${encodeURIComponent(token)}` : ''
  return url.toString()
}

// Opens a WebSocket that reconnects by itself. Returns the function that closes it.
// - alMensaje(datos): every message, already parsed
// - alReconectar(): the connection came back; reload so no change is lost
// - alCambiarConexion(conectado): to show the user if the page is live
export function conectarSocket(ruta, { alMensaje, alReconectar, alCambiarConexion } = {}) {
  let socket
  let temporizador
  let intento = 0
  let cerrado = false

  function abrir() {
    socket = new WebSocket(urlSocket(ruta, leerSesion()?.token))
    socket.addEventListener('open', () => {
      alCambiarConexion?.(true)
      if (intento > 0) alReconectar?.()
      intento = 0
    })
    socket.addEventListener('message', (evento) => alMensaje?.(JSON.parse(evento.data)))
    socket.addEventListener('close', (evento) => {
      alCambiarConexion?.(false)
      if (cerrado || SIN_PERMISO.includes(evento.code)) return
      temporizador = setTimeout(abrir, esperaReconexion(intento))
      intento += 1
    })
  }

  abrir()
  return () => {
    cerrado = true
    clearTimeout(temporizador)
    socket.close()
  }
}
