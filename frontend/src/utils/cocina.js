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

// HU-32 · Ordena las tarjetas situando las más antiguas primero (criterio 2)
export function ordenarPorAntiguedad(tarjetas) {
  return [...tarjetas].sort((a, b) => {
    const diff = new Date(a.recibido_en).getTime() - new Date(b.recibido_en).getTime()
    return diff !== 0 ? diff : a.id - b.id
  })
}

// HU-32 · Estado del cronómetro dinámico y semáforo de color (criterios 1 y 3)
export function estadoCronometroCocina(tarjeta, ahora) {
  const detenido = tarjeta.estado === 'listo_despacho' || Boolean(tarjeta.listo_en)

  if (detenido) {
    const fin = tarjeta.listo_en ? new Date(tarjeta.listo_en).getTime() : ahora
    const minutos = minutosEntre(tarjeta.recibido_en, fin)
    return {
      minutos,
      detenido: true,
      etiqueta: `Listo en ${textoDuracion(minutos)}`,
      clases: 'border-borde bg-superficie text-texto-suave',
    }
  }

  const minutos = minutosEntre(tarjeta.recibido_en, ahora)
  let clases = 'border-exito bg-exito/15 text-exito' // < 10 min: a tiempo
  if (minutos >= 20) {
    clases = 'border-error bg-error/15 text-error' // >= 20 min: crítico / retrasado
  } else if (minutos >= 10) {
    clases = 'border-aviso bg-aviso/15 text-aviso' // 10 - 19 min: atención
  }

  return {
    minutos,
    detenido: false,
    etiqueta: textoDuracion(minutos),
    clases,
  }
}

// Compatibilidad con llamadas previas
export function textoTiempoEnCocina(tarjeta, ahora) {
  const { detenido, minutos } = estadoCronometroCocina(tarjeta, ahora)
  if (detenido) {
    return `Preparado en ${textoDuracion(minutos)}`
  }
  return `En cocina hace ${textoDuracion(minutos)}`
}