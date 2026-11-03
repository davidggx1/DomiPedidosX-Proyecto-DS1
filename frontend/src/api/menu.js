import api from './cliente.js'

// Peticiones de la gestión del menú (HU-76 y HU-77). Cada función devuelve los datos de la respuesta.

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

// activo: true (solo activos, por defecto), false (solo eliminados) o 'todos'.
export async function listarInsumos({ activo } = {}) {
  const params = activo === undefined ? {} : { activo }
  const { data } = await api.get('/menu/insumos/', { params })
  return data
}

export async function crearInsumo(datos) {
  const { data } = await api.post('/menu/insumos/', datos)
  return data
}

export async function actualizarInsumo(id, datos) {
  const { data } = await api.patch(`/menu/insumos/${id}/`, datos)
  return data
}

// Borrado lógico: el ingrediente queda inactivo y se puede restaurar.
export async function eliminarInsumo(id) {
  await api.delete(`/menu/insumos/${id}/`)
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

export async function listarIngredientesProducto(productoId) {
  const { data } = await api.get(`/menu/productos/${productoId}/ingredientes/`)
  return data
}

export async function agregarIngrediente(productoId, datos) {
  const { data } = await api.post(`/menu/productos/${productoId}/ingredientes/`, datos)
  return data
}

export async function actualizarIngrediente(productoId, vinculoId, datos) {
  const { data } = await api.patch(`/menu/productos/${productoId}/ingredientes/${vinculoId}/`, datos)
  return data
}

export async function quitarIngrediente(productoId, vinculoId) {
  await api.delete(`/menu/productos/${productoId}/ingredientes/${vinculoId}/`)
}

// --- Menú del cliente (HU-18). Rutas públicas: no requieren sesión. ---

export async function listarSedesMenu() {
  const { data } = await api.get('/menu/sedes/')
  return data
}

// Devuelve { sede, categorias: [{ id, nombre, productos: [...] }] }.
export async function obtenerMenuSede(sedeId) {
  const { data } = await api.get(`/menu/sedes/${sedeId}/menu/`)
  return data
}
