import api from './cliente.js'
import { conectarSocket } from './tiempoReal.js'

// Stock requests (HU-14). `tipo` is 'productos' or 'insumos'

// The operador only gets the records of its own sede
export async function listarExistencias(tipo, { sede } = {}) {
  const params = sede ? { sede } : {}
  const { data } = await api.get(`/inventario/${tipo}/`, { params })
  return data
}

export async function registrarExistencias(tipo, datos) {
  const { data } = await api.post(`/inventario/${tipo}/`, datos)
  return data
}

export async function ajustarExistencias(tipo, id, datos) {
  const { data } = await api.patch(`/inventario/${tipo}/${id}/`, datos)
  return data
}

// Hard delete: the item is not stocked in the sede until it is registered again
export async function quitarExistencias(tipo, id) {
  await api.delete(`/inventario/${tipo}/${id}/`)
}

// HU-16: low stock alerts of the sede of the operator (an admin gets every sede).
// `estado` is 'activa' (default), 'resuelta' or 'todas'
export async function listarAlertasInventario(estado = 'activa') {
  const { data } = await api.get('/inventario/alertas/', { params: { estado } })
  return data
}

// HU-16: the stock alerts travel in the same socket as the incoming orders.
// Returns the function that closes it
export function conectarAlertasInventario(eventos) {
  return conectarSocket('/ws/pedidos/entrantes/', eventos)
}
