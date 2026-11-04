import api from './cliente.js'

// Direcciones de entrega del cliente con sesión (HU-06). Cada función devuelve los datos de la respuesta.

export async function listarDirecciones() {
  const { data } = await api.get('/usuarios/direcciones/')
  return data
}

// datos: { alias, direccion, barrio, latitud, longitud, es_principal }
export async function crearDireccion(datos) {
  const { data } = await api.post('/usuarios/direcciones/', datos)
  return data
}

export async function actualizarDireccion(id, datos) {
  const { data } = await api.patch(`/usuarios/direcciones/${id}/`, datos)
  return data
}

// Borrado lógico: deja de listarse, pero los pedidos anteriores conservan su copia.
export async function eliminarDireccion(id) {
  await api.delete(`/usuarios/direcciones/${id}/`)
}
