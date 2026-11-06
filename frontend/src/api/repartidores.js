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
