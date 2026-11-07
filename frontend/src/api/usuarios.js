import api from './cliente.js'

// HU-08: Registrar empleado por el Administrador
export async function registrarEmpleado(datos) {
  const { data } = await api.post('/usuarios/empleados/', datos)
  return data
}

// HU-08 / Dashboard Admin: Listar empleados registrados
export async function listarEmpleados() {
  const { data } = await api.get('/usuarios/empleados/')
  return data
}
// HU-07: perfil del cliente (nombres, apellidos y celular se pueden editar)
export async function obtenerPerfil() {
  const { data } = await api.get('/usuarios/perfil/')
  return data
}

export async function actualizarPerfil(datos) {
  const { data } = await api.patch('/usuarios/perfil/', datos)
  return data
}
