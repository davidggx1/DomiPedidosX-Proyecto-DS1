import api from './cliente.js'
import { conectarSocket } from './tiempoReal.js'

// Own availability of the repartidor (HU-41)
export async function obtenerMiDisponibilidad() {
  const { data } = await api.get('/usuarios/repartidor/disponibilidad/')
  return data
}

export async function cambiarMiDisponibilidad(disponible) {
  const { data } = await api.patch('/usuarios/repartidor/disponibilidad/', { disponible })
  return data
}

// Orders in progress assigned to the repartidor (HU-42)
export async function listarMisEntregas() {
  const { data } = await api.get('/pedidos/mis-entregas/')
  return data
}

// Tells when the list changes (an order assigned, removed or moved). Returns the close function
export function conectarMisEntregas(eventos) {
  return conectarSocket('/ws/pedidos/mis-entregas/', eventos)
}

// Detail of one delivery: address, products, totals and payment (HU-43)
export async function obtenerEntrega(id) {
  const { data } = await api.get(`/pedidos/mis-entregas/${id}/`)
  return data
}

// Next step of the delivery; with cash, the amount received from the customer (HU-45)
export async function actualizarEntrega(id, estado, montoRecaudado = null) {
  const cuerpo = montoRecaudado == null ? { estado } : { estado, monto_recaudado: montoRecaudado }
  const { data } = await api.patch(`/pedidos/mis-entregas/${id}/entrega/`, cuerpo)
  return data
}
