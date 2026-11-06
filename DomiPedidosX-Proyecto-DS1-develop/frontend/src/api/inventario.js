import api from './cliente.js'

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
