import api from './cliente.js'

// Detail of one order to prepare it (HU-30): lines, additions, removed ingredients and notes
export async function obtenerComanda(id) {
  const { data } = await api.get(`/pedidos/${id}/cocina/`)
  return data
}

// HU-17 · Products of the kitchen's sede and whether they can be ordered
export async function listarProductosCocina(q = '') {
  const params = q.trim() ? { q: q.trim() } : {}
  const { data } = await api.get('/menu/cocina/productos/', { params })
  return data
}

// HU-17 · Takes the product out of the sede's menu and warns the operator
export async function marcarAgotado(id) {
  const { data } = await api.post(`/menu/cocina/productos/${id}/agotado/`)
  return data
}
