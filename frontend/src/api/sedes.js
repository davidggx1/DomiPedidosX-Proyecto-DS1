import api from './cliente.js'

// With `sedeId` (the sede of the cart) the answer is about that sede, the one the
// order goes to. If it does not cover the address but another one does, it answers
// cubierto: false with codigo 'otra_sede' and sede_sugerida
export async function validarCoberturaDireccion(latitud, longitud, sedeId) {
  const cuerpo = { latitud, longitud, ...(sedeId ? { sede_id: Number(sedeId) } : {}) }
  const { data } = await api.post('/sedes/validar-cobertura/', cuerpo)
  return data
}

export async function listarSedes() {
  const { data } = await api.get('/sedes/')
  return Array.isArray(data) ? data : (data?.results ?? [])
}