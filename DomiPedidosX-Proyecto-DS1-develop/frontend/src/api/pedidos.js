import api from './cliente.js'

export async function obtenerTableroCocina() {
  const respuesta = await api.get('/pedidos/cocina/tablero/')
  return respuesta.data
}

export async function obtenerComandaCocina(pedidoId) {
  const respuesta = await api.get(`/pedidos/${pedidoId}/cocina/`)
  return respuesta.data
}

export async function cambiarEstadoPedido(pedidoId, estado, motivo = '') {
  const respuesta = await api.patch(`/pedidos/${pedidoId}/estado/`, { estado, motivo })
  return respuesta.data
}

export function crearUrlWebSocketCocina(token) {
  const apiUrl = new URL(import.meta.env.VITE_API_URL ?? 'http://127.0.0.1:8000/api')
  const protocolo = apiUrl.protocol === 'https:' ? 'wss:' : 'ws:'
  return `${protocolo}//${apiUrl.host}/ws/pedidos/cocina/?token=${encodeURIComponent(token)}`
}
