// Sede a la que va el carrito, para mostrarla en el carrito y al confirmar el pedido.
// Mismo texto que el selector de sede del menú: "Sede Centro · San Pedro".

export function nombreSede(sede) {
  if (!sede) return ''
  return sede.barrio ? `${sede.nombre} · ${sede.barrio}` : sede.nombre
}

// La sede del carrito dentro de la lista de sedes (el id puede venir como texto)
export function buscarSede(sedes, sedeId) {
  if (!sedeId || !Array.isArray(sedes)) return null
  return sedes.find((sede) => String(sede.id) === String(sedeId)) ?? null
}
