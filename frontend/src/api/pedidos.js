import api from './cliente.js'
import { conectarSocket } from './tiempoReal.js'

export async function obtenerTableroCocina(sede) {
  const params = sede ? { sede } : {}
  const { data } = await api.get('/pedidos/cocina/tablero/', { params })
  return data
}

export async function cambiarEstadoPedido(id, estado, motivo = '') {
  const { data } = await api.patch(`/pedidos/${id}/estado/`, { estado, motivo })
  return data
}

// Current state, history with the time of each step and next possible states
export async function obtenerEstadoPedido(id) {
  const { data } = await api.get(`/pedidos/${id}/estado/`)
  return data
}

// Every state change of one order, live (HU-47). Same events as alMensaje in conectarSocket
export function conectarEstadoPedido(id, eventos) {
  return conectarSocket(`/ws/pedidos/${id}/estado/`, eventos)
}

// Orders of the logged customer: the ones in progress first (HU-47)
export async function listarMisPedidos() {
  const { data } = await api.get('/pedidos/mios/')
  return data
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

// Orders of today by sede, counted by state (HU-67)
export async function obtenerResumenDia() {
  const { data } = await api.get('/pedidos/resumen-dia/')
  return data
}
