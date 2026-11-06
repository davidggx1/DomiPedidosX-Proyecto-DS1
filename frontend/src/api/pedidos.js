import api from './cliente.js'

export async function obtenerTableroCocina(sede) {
  const params = sede ? { sede } : {}
  const { data } = await api.get('/pedidos/cocina/tablero/', { params })
  return data
}

export async function cambiarEstadoPedido(id, estado, motivo = '') {
  const { data } = await api.patch(`/pedidos/${id}/estado/`, { estado, motivo })
  return data
}

export function conectarEstadoPedido(id, onChange) {
  const base = import.meta.env.VITE_API_URL || window.location.origin
  const url = new URL(base)
  url.protocol = url.protocol === 'https:' ? 'wss:' : 'ws:'
  url.pathname = `/ws/pedidos/${id}/estado/`
  const socket = new WebSocket(url)
  socket.addEventListener('message', (event) => onChange(JSON.parse(event.data)))
  return () => socket.close()
}
