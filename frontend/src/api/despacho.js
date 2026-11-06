import api from './cliente.js'

// Orders "listo para despacho" that go to a home, with their repartidor if they have one (HU-35)
export async function listarPedidosDespacho(sede) {
  const params = sede ? { sede } : {}
  const { data } = await api.get('/pedidos/despacho/', { params })
  return data
}

// Repartidores of the sede with their availability and how many deliveries they carry
export async function listarRepartidores({ disponible } = {}) {
  const params = disponible === undefined ? {} : { disponible }
  const { data } = await api.get('/usuarios/repartidores/', { params })
  return data
}

export async function asignarRepartidor(pedidoId, repartidorId) {
  const { data } = await api.post(`/pedidos/${pedidoId}/repartidor/`, { repartidor: repartidorId })
  return data
}

// Only works before the repartidor picks the order up
export async function retirarRepartidor(pedidoId) {
  const { data } = await api.delete(`/pedidos/${pedidoId}/repartidor/`)
  return data
}
