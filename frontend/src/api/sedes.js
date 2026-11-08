import api from './cliente.js'

export async function validarCoberturaDireccion(latitud, longitud) {
  const { data } = await api.post('/sedes/validar-cobertura/', { latitud, longitud })
  return data
}