import api from './cliente.js'

// HU-85 · Combos de la sede del operador (el administrador ve todas; ?sede= filtra).
export async function listarCombos(params = {}) {
  const { data } = await api.get('/combos/', { params })
  return data
}

// datos: { nombre, precio, fecha_inicio, fecha_vencimiento, productos: [{ producto, cantidad }], ... }
export async function crearCombo(datos) {
  const { data } = await api.post('/combos/', datos)
  return data
}

export async function actualizarCombo(id, datos) {
  const { data } = await api.patch(`/combos/${id}/`, datos)
  return data
}

// Desactiva (no borra): el combo deja de ofrecerse pero conserva su historial.
export async function desactivarCombo(id) {
  await api.delete(`/combos/${id}/`)
}