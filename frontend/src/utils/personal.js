// HU-80 · Lógica de la edición del personal sin React, para poder probarla con Vitest.
//
// El detalle de un empleado llega así (GET /api/usuarios/empleados/<id>/):
// { id, email, nombres, apellidos, tipo_documento, num_documento, celular, direccion,
//   rol: 'OPERADOR' | 'COCINA' | 'REPARTIDOR' | 'ADMINISTRADOR', sede_id, sede, activa }

export const ROLES_PERSONAL = [
  { valor: 'OPERADOR', etiqueta: 'Operador de sede' },
  { valor: 'COCINA', etiqueta: 'Cocina' },
  { valor: 'REPARTIDOR', etiqueta: 'Repartidor' },
  { valor: 'ADMINISTRADOR', etiqueta: 'Administrador' },
]

export const TIPOS_DOCUMENTO = [
  { valor: 'CC', etiqueta: 'Cédula de ciudadanía' },
  { valor: 'TI', etiqueta: 'Tarjeta de identidad' },
  { valor: 'CE', etiqueta: 'Cédula de extranjería' },
  { valor: 'PA', etiqueta: 'Pasaporte' },
  { valor: 'RC', etiqueta: 'Registro civil' },
  { valor: 'PPT', etiqueta: 'Permiso por Protección Temporal' },
]

export function etiquetaRol(rol) {
  return ROLES_PERSONAL.find((opcion) => opcion.valor === String(rol ?? '').toUpperCase())?.etiqueta ?? 'Sin rol'
}

export function soloDigitos(texto) {
  return String(texto ?? '').replace(/\D/g, '')
}

export function requiereSede(rol) {
  return rol !== 'ADMINISTRADOR'
}

export function datosInicialesEmpleado(empleado) {
  return {
    nombres: empleado.nombres ?? '',
    apellidos: empleado.apellidos ?? '',
    tipo_documento: empleado.tipo_documento ?? 'CC',
    num_documento: empleado.num_documento ?? '',
    celular: empleado.celular ?? '',
    direccion: empleado.direccion ?? '',
    rol: String(empleado.rol ?? '').toUpperCase(),
    sede_id: empleado.sede_id == null ? '' : String(empleado.sede_id),
  }
}

// Devuelve { campo: 'mensaje' }; vacío significa que todo está bien.
// Son las mismas reglas del backend: el servidor vuelve a validar.
export function validarEmpleado(datos) {
  const errores = {}
  if (!String(datos.nombres ?? '').trim()) errores.nombres = 'Escribe los nombres.'
  if (!String(datos.apellidos ?? '').trim()) errores.apellidos = 'Escribe los apellidos.'
  if (!String(datos.num_documento ?? '').trim()) errores.num_documento = 'Escribe el número de documento.'
  else if (String(datos.num_documento).trim().length > 12) {
    errores.num_documento = 'El documento no puede tener más de 12 caracteres.'
  }
  if (!/^\d{10}$/.test(String(datos.celular ?? ''))) {
    errores.celular = 'El celular debe tener exactamente 10 dígitos.'
  }
  if (!String(datos.direccion ?? '').trim()) errores.direccion = 'Escribe la dirección.'
  if (!ROLES_PERSONAL.some((opcion) => opcion.valor === datos.rol)) errores.rol = 'Elige un rol.'
  if (requiereSede(datos.rol) && !datos.sede_id) errores.sede_id = 'Elige la sede para este rol.'
  return errores
}

// Cuerpo del PATCH. Un administrador no lleva sede.
export function armarCuerpoEmpleado(datos) {
  return {
    nombres: datos.nombres.trim(),
    apellidos: datos.apellidos.trim(),
    tipo_documento: datos.tipo_documento,
    num_documento: datos.num_documento.trim(),
    celular: datos.celular,
    direccion: datos.direccion.trim(),
    rol: datos.rol,
    sede_id: requiereSede(datos.rol) ? Number(datos.sede_id) : null,
  }
}

// Texto que resume lo que cambia en los permisos, para avisar al administrador antes de guardar.
export function cambiosDeAcceso(original, datos, sedes = []) {
  const nombreSede = (id) => sedes.find((sede) => String(sede.id) === String(id))?.nombre ?? 'otra sede'
  const cambios = []
  if (String(original.rol).toUpperCase() !== datos.rol) {
    cambios.push(`rol: ${etiquetaRol(original.rol)} → ${etiquetaRol(datos.rol)}`)
  }
  const sedeNueva = requiereSede(datos.rol) ? datos.sede_id : ''
  const sedeVieja = original.sede_id == null ? '' : String(original.sede_id)
  if (sedeNueva !== sedeVieja) {
    cambios.push(`sede: ${original.sede ?? 'ninguna'} → ${sedeNueva ? nombreSede(sedeNueva) : 'ninguna'}`)
  }
  return cambios
}

export function claseEstadoCuenta(activa) {
  return activa ? 'border-exito text-exito' : 'border-aviso text-aviso'
}

// La lista devuelve la sede como texto ("N/A" para quien no tiene).
export function textoSede(empleado) {
  const sede = typeof empleado.sede === 'string' ? empleado.sede : empleado.sede?.nombre
  return sede && sede !== 'N/A' ? sede : null
}