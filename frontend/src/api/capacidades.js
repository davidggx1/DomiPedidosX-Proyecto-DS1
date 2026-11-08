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