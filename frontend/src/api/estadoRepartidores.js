import api from './cliente.js'
import { conectarSocket } from './tiempoReal.js'

// HU-37 · Repartidores de la sede con su estado, su carga y los pedidos que llevan
export async function obtenerEstadoRepartidores() {
  const { data } = await api.get('/pedidos/repartidores/estado/')
  return data
}

// Avisa cuando algo cambia (asignación, estado de un pedido o disponibilidad).
// El aviso no trae datos: el tablero vuelve a pedir la lista. Devuelve la función que cierra.
export function conectarEstadoRepartidores(eventos) {
  return conectarSocket('/ws/pedidos/repartidores/', eventos)
}