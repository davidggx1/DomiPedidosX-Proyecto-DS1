// HU-11 · Data the product form sends to the server

function mismasSedes(a, b) {
  return a.length === b.length && a.every((id) => b.includes(id))
}

// `valores` are the fields of the form, `producto` is the one being edited (if any).
// HU-14: the stock control type travels both when creating and when editing
export function armarDatosProducto({ valores, archivo, producto }) {
  const esEdicion = Boolean(producto)
  const datos = new FormData()
  datos.append('nombre', valores.nombre.trim())
  datos.append('descripcion', valores.descripcion.trim())
  datos.append('precio_base', valores.precio_base)
  datos.append('tiempo_preparacion', valores.tiempo_preparacion)
  datos.append('categoria', valores.categoria)
  datos.append('tipo_control_stock', valores.tipo_control_stock)
  if (esEdicion) datos.append('activo', String(valores.activo))
  if (archivo) datos.append('imagen', archivo)
  // When editing, the sedes are sent only if they changed, to keep the current availability
  const sedesIniciales = producto?.sedes.map(String) ?? []
  if (!esEdicion || !mismasSedes(valores.sedes, sedesIniciales)) {
    valores.sedes.forEach((id) => datos.append('sedes', id))
  }
  return datos
}
