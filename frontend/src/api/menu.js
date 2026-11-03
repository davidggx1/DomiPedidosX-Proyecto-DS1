import api from './cliente.js'

// Peticiones de la gestión del menú (HU-76). Cada función devuelve los datos de la respuesta.

// activa: true (solo activas), false (solo eliminadas) o undefined (todas).
export async function listarAdiciones({ activa } = {}) {
  const params = activa === undefined ? {} : { activa }
  const { data } = await api.get('/menu/adiciones/', { params })
  return data
}

export async function crearAdicion(datos) {
  const { data } = await api.post('/menu/adiciones/', datos)
  return data
}

export async function actualizarAdicion(id, datos) {
  const { data } = await api.patch(`/menu/adiciones/${id}/`, datos)
  return data
}

// Borrado lógico: la adición queda inactiva y los pedidos anteriores no cambian.
export async function eliminarAdicion(id) {
  await api.delete(`/menu/adiciones/${id}/`)
}

export async function listarInsumos() {
  const { data } = await api.get('/menu/insumos/')
  return data
}

export async function listarProductosOpciones() {
  const { data } = await api.get('/menu/productos-opciones/')
  return data
}

export async function listarAdicionesProducto(productoId) {
  const { data } = await api.get(`/menu/productos/${productoId}/adiciones/`)
  return data
}

export async function asignarAdicion(productoId, datos) {
  const { data } = await api.post(`/menu/productos/${productoId}/adiciones/`, datos)
  return data
}

export async function quitarAdicionProducto(productoId, vinculoId) {
  await api.delete(`/menu/productos/${productoId}/adiciones/${vinculoId}/`)
}
