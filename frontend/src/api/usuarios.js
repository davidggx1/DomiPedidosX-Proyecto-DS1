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