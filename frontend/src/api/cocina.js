import api from './cliente.js'

// Detail of one order to prepare it (HU-30): lines, additions, removed ingredients and notes
export async function obtenerComanda(id) {
  const { data } = await api.get(`/pedidos/${id}/cocina/`)
  return data
}
