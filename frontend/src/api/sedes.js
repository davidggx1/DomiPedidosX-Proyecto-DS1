import api from './cliente.js'

export async function validarCoberturaDireccion(latitud, longitud) {
  const { data } = await api.post('/sedes/validar-cobertura/', { latitud, longitud })
  return data
}

export async function listarSedes() {
  const { data } = await api.get('/sedes/')
  return Array.isArray(data) ? data : (data?.results ?? [])
}