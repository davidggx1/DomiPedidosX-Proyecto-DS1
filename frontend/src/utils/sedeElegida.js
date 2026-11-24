// Sede elegida en el menú, recordada en este navegador para la próxima visita (HU-18).
// La usa también "Repetir pedido" (HU-26) para abrir el menú en la sede del pedido.
const CLAVE_SEDE = 'domipedidosx.sede'

export function leerSedeGuardada() {
  try {
    return localStorage.getItem(CLAVE_SEDE) ?? ''
  } catch {
    return ''
  }
}

export function guardarSede(sedeId) {
  try {
    localStorage.setItem(CLAVE_SEDE, String(sedeId))
  } catch {
    // Sin almacenamiento disponible: se vuelve a elegir en la próxima visita.
  }
}
