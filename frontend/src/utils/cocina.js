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

// "Clásica" -> "clasica", to search without caring about accents or case
function normalizar(texto) {
  return texto.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase().trim()
}

// HU-17 · Products whose name or category contain the search. Sold out ones go last
export function filtrarProductosCocina(productos, busqueda) {
  const termino = normalizar(busqueda)
  const encontrados = termino
    ? productos.filter((p) => normalizar(`${p.nombre} ${p.categoria}`).includes(termino))
    : productos
  return [...encontrados].sort((a, b) => Number(b.disponible) - Number(a.disponible))
}

// HU-33 · Same limits as the backend (pedidos/cancelacion.py)
export const JUSTIFICACION_MINIMA = 5
export const JUSTIFICACION_MAXIMA = 500

// Error text for the justification of a kitchen error, or null if it is valid
export function validarJustificacion(texto) {
  const limpio = (texto ?? '').trim()
  if (!limpio) return 'Escribe la justificación del error de cocina.'
  if (limpio.length < JUSTIFICACION_MINIMA) {
    return `La justificación debe tener al menos ${JUSTIFICACION_MINIMA} caracteres.`
  }
  if (limpio.length > JUSTIFICACION_MAXIMA) {
    return `La justificación no puede superar ${JUSTIFICACION_MAXIMA} caracteres.`
  }
  return null
}

// HU-17 · Names of the products that were unavailable and now can be ordered
// again (the operator enabled them). Empty on the first load
export function productosReactivados(antes, despues) {
  if (!antes) return []
  const noDisponibles = new Set(antes.filter((p) => !p.disponible).map((p) => p.id))
  return despues.filter((p) => p.disponible && noDisponibles.has(p.id)).map((p) => p.nombre)
}

// HU-39 · Line about the courier on a "listo para despacho" card, or null when it does not apply.
// tono: 'exito' (arrived: hand the order over), 'espera' (on the way) or 'aviso' (nobody assigned yet)
export function avisoRepartidor(tarjeta) {
  if (tarjeta.estado !== 'listo_despacho' || !tarjeta.lleva_domicilio) return null
  if (!tarjeta.repartidor) {
    return { tono: 'aviso', texto: 'Sin repartidor asignado todavía' }
  }
  if (tarjeta.repartidor_llego_en) {
    const hora = new Date(tarjeta.repartidor_llego_en).toLocaleTimeString('es-CO', {
      hour: '2-digit',
      minute: '2-digit',
    })
    return { tono: 'exito', texto: `${tarjeta.repartidor} llegó a las ${hora}: entrégale el pedido` }
  }
  return { tono: 'espera', texto: `${tarjeta.repartidor} va en camino a la sede` }
}
