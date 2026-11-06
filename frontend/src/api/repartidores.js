import api from './cliente.js'

// Own availability of the repartidor (HU-41)
export async function obtenerMiDisponibilidad() {
  const { data } = await api.get('/usuarios/repartidor/disponibilidad/')
  return data
}

export async function cambiarMiDisponibilidad(disponible) {
  const { data } = await api.patch('/usuarios/repartidor/disponibilidad/', { disponible })
  return data
}
