import api from './cliente.js'

export async function obtenerCapacidadesSede(sedeId) {
  const { data } = await api.get(`/capacidades/?sede=${sedeId}`)
  return data
}

export async function guardarCapacidad(payload) {
  if (payload.id) {
    const { data } = await api.put(`/capacidades/${payload.id}/`, payload)
    return data
  }
  const { data } = await api.post('/capacidades/', payload)
  return data
}

export async function eliminarCapacidad(id) {
  await api.delete(`/capacidades/${id}/`)
}
// HU-61: current capacity of a sede, the operator gets his own sede without params
export async function obtenerEstadoCapacidad(sedeId) {
  const params = sedeId ? { sede: sedeId } : {}
  const { data } = await api.get('/pedidos/capacidad/', { params })
  return data
}
