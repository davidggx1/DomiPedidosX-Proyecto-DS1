import api from './cliente.js'

// La lista puede venir paginada ({ results }) o como arreglo simple.
const comoLista = (data) => (Array.isArray(data) ? data : (data.results ?? []))

export async function listarZonas(sedeId) {
  const { data } = await api.get('/zonas-cobertura/', { params: { sede: sedeId } })
  return comoLista(data)
}

export async function crearZona(datos) {
  const { data } = await api.post('/zonas-cobertura/', datos)
  return data
}

export async function actualizarZona(id, datos) {
  const { data } = await api.patch(`/zonas-cobertura/${id}/`, datos)
  return data
}

export async function eliminarZona(id) {
  await api.delete(`/zonas-cobertura/${id}/`)
}