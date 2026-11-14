// HU-37 · Lógica del tablero de repartidores, sin React, para poder probarla con Vitest.
//
// Cada repartidor llega del backend así:
// {
//   id, nombres, apellidos, celular, disponible,
//   estado: 'disponible' | 'no_disponible' | 'en_entrega', estado_nombre, carga,
//   pedidos: [{ id, numero_pedido, estado, estado_nombre, avance: { paso, total },
//               entrega_direccion, entrega_barrio, tiempo_estimado_entrega }],
// }

export const FILTROS = [
  { valor: 'todos', etiqueta: 'Todos' },
  { valor: 'disponible', etiqueta: 'Disponibles' },
  { valor: 'en_entrega', etiqueta: 'En entrega' },
  { valor: 'no_disponible', etiqueta: 'No disponibles' },
]

// Cuántos repartidores hay en cada estado, para los contadores de los filtros.
export function contarPorEstado(repartidores) {
  const conteo = { todos: repartidores.length, disponible: 0, en_entrega: 0, no_disponible: 0 }
  for (const repartidor of repartidores) {
    if (repartidor.estado in conteo) conteo[repartidor.estado] += 1
  }
  return conteo
}

export function filtrarPorEstado(repartidores, filtro) {
  if (!filtro || filtro === 'todos') return repartidores
  return repartidores.filter((repartidor) => repartidor.estado === filtro)
}

export function textoCarga(carga) {
  if (!carga) return 'Sin entregas'
  return carga === 1 ? '1 entrega' : `${carga} entregas`
}

export function nombreCompleto(repartidor) {
  return `${repartidor.nombres} ${repartidor.apellidos}`.trim()
}

// Colores de la etiqueta de estado (clases de Tailwind que ya usa el proyecto).
export function claseEstado(estado) {
  if (estado === 'disponible') return 'border-exito text-exito'
  if (estado === 'en_entrega') return 'border-aviso text-aviso'
  return 'border-borde text-texto-suave'
}

// Avance de un pedido: paso 0 significa que no es parte del recorrido de entrega.
export function porcentajeAvance({ paso, total }) {
  if (!total || paso <= 0) return 0
  return Math.min(100, Math.round((paso / total) * 100))
}

export function textoAvance({ paso, total }) {
  return paso > 0 ? `Paso ${paso} de ${total}` : 'En proceso'
}