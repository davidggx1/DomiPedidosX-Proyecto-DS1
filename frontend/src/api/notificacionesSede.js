import api from './cliente.js'

// HU-83: quién recibe por correo los avisos de cada sede (solo administrador)
export async function obtenerSuscripciones(sedeId) {
  const { data } = await api.get('/notificaciones-sede/', { params: { sede: sedeId } })
  return data
}

// payload = { sede, evento, rol } o { sede, evento, correo }
export async function crearSuscripcion(payload) {
  const { data } = await api.post('/notificaciones-sede/', payload)
  return data
}

export async function eliminarSuscripcion(id) {
  await api.delete(`/notificaciones-sede/${id}/`)
}
