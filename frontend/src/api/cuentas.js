import api from './cliente.js'

// Gestión de cuentas del administrador (HU-09).

// filtros: { tipo: 'cliente' | 'personal', activa: true | false, buscar: 'texto' }.
// Los filtros vacíos no se envían.
export async function listarCuentas(filtros = {}) {
  const params = Object.fromEntries(
    Object.entries(filtros).filter(([, valor]) => valor !== '' && valor !== undefined),
  )
  const { data } = await api.get('/usuarios/cuentas/', { params })
  return data
}

// activa = false desactiva la cuenta; true la reactiva.
export async function cambiarEstadoCuenta(id, activa) {
  const { data } = await api.patch(`/usuarios/cuentas/${id}/`, { activa })
  return data
}
