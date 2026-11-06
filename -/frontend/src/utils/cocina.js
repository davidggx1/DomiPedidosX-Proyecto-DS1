import { minutosEntre, textoDuracion } from './tiempo.js'

// Columns of the kitchen board, in the order the order moves through them
export const COLUMNAS_COCINA = [
  { estado: 'recibido', titulo: 'Recibido' },
  { estado: 'en_preparacion', titulo: 'En preparación' },
  { estado: 'listo_despacho', titulo: 'Listo para despacho' },
]

// The one step forward the kitchen can give from each column
export const AVANCE_COCINA = {
  recibido: { estado: 'en_preparacion', texto: 'Iniciar preparación' },
  en_preparacion: { estado: 'listo_despacho', texto: 'Marcar como listo' },
}

// The count stops when the order is ready (the timer of HU-32 ends there)
export function textoTiempoEnCocina(tarjeta, ahora) {
  if (tarjeta.listo_en) {
    const total = minutosEntre(tarjeta.recibido_en, new Date(tarjeta.listo_en).getTime())
    return `Preparado en ${textoDuracion(total)}`
  }
  return `En cocina hace ${textoDuracion(minutosEntre(tarjeta.recibido_en, ahora))}`
}
