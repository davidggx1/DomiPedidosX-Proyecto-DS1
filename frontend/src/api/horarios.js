import api from './cliente.js'

export async function obtenerHorariosSede(sedeId) {
  const { data } = await api.get(`/horarios/?sede=${sedeId}`)
  return data
}

export async function guardarHorario(datos) {
  if (datos.id) {
    const { data } = await api.put(`/horarios/${datos.id}/`, datos)
    return data
  }
  const { data } = await api.post('/horarios/', datos)
  return data
}

export async function eliminarHorario(id) {
  await api.delete(`/horarios/${id}/`)
}

export async function obtenerFeriadosSede(sedeId) {
  const { data } = await api.get(`/feriados/?sede=${sedeId}`)
  return data
}

export async function guardarFeriado(datos) {
  if (datos.id) {
    const { data } = await api.put(`/feriados/${datos.id}/`, datos)
    return data
  }
  const { data } = await api.post('/feriados/', datos)
  return data
}

export async function eliminarFeriado(id) {
  await api.delete(`/feriados/${id}/`)
}