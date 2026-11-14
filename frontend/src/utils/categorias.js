// HU-78: delete menu categories

export function textoProductos(total) {
  return total === 1 ? '1 producto' : `${total} productos`
}

// Why a category cannot be deleted, or null if it can. The server checks it too,
// this only lets the modal explain it before asking
export function motivoNoEliminar(categoria) {
  const total = categoria?.total_productos ?? 0
  if (total === 0) return null
  const asociados = total === 1 ? 'asociado' : 'asociados'
  return `Tiene ${textoProductos(total)} ${asociados}. Muévelos a otra categoría antes de eliminarla.`
}
