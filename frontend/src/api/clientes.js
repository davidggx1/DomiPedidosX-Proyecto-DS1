import api from './cliente.js'

// Información de clientes para el administrador (HU-69).

// texto: nombre, apellido, correo o celular. Vacío trae todos.
export async function buscarClientes(texto = '') {
  const params = texto ? { buscar: texto } : {}
  const { data } = await api.get('/usuarios/clientes/', { params })
  return data
}

// Ficha con contacto, direcciones e historial de pedidos.
export async function obtenerFichaCliente(id) {
  const { data } = await api.get(`/usuarios/clientes/${id}/`)
  return data
}
