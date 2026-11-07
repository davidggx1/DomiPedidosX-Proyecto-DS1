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

export async function crearPedidoOperador(datosPedido) {
  const { data } = await api.post('/pedidos/operador/crear/', datosPedido)
  return data
}

// HU-23: Confirmación de pedido por el Cliente
export async function confirmarPedidoCliente(payload) {
  const { data } = await api.post('/pedidos/confirmar/', payload)
  return data
}

// HU-27: Carga inicial de pedidos entrantes
export async function obtenerPedidosEntrantes() {
  const { data } = await api.get('/pedidos/entrantes/')
  return data
}