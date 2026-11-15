import api from './cliente.js'

// HU-84 · Promociones de la sede del operador.
// estado: 'vigente' | 'programada' | 'vencida' | 'inactiva'. Sin filtros trae todas.
export async function listarPromociones(params = {}) {
  const { data } = await api.get('/promociones/', { params })
  return data
}

export async function crearPromocion(datos) {
  const { data } = await api.post('/promociones/', datos)
  return data
}

export async function actualizarPromocion(id, datos) {
  const { data } = await api.patch(`/promociones/${id}/`, datos)
  return data
}

// Desactiva (no borra): la promoción deja de poder usarse pero conserva su historial.
export async function desactivarPromocion(id) {
  await api.delete(`/promociones/${id}/`)
}