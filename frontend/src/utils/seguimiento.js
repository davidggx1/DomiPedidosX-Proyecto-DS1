// Steps of the progress bar the customer sees (HU-47), in the order the order moves
export const PASOS_CLIENTE = [
  { estado: 'pendiente_aprobacion', titulo: 'Pedido enviado', texto: 'La sede está revisando tu pedido.' },
  { estado: 'recibido', titulo: 'Confirmado', texto: 'La sede aprobó tu pedido.' },
  { estado: 'en_preparacion', titulo: 'En preparación', texto: 'La cocina está preparando tu pedido.' },
  { estado: 'listo_despacho', titulo: 'Listo', texto: 'Tu pedido espera al repartidor.' },
  { estado: 'recogido', titulo: 'Recogido', texto: 'El repartidor ya tiene tu pedido.' },
  { estado: 'en_camino', titulo: 'En camino', texto: 'El repartidor va hacia tu dirección.' },
  { estado: 'entregado', titulo: 'Entregado', texto: '¡Disfruta tu pedido!' },
]

// Each step with its situation (hecho, actual, pendiente) and the time it happened.
// Orders made by the operator start already "recibido": earlier steps count as done
export function pasosConProgreso(estado, historial = []) {
  const actual = PASOS_CLIENTE.findIndex((paso) => paso.estado === estado)
  return PASOS_CLIENTE.map((paso, indice) => {
    const registro = historial.find((item) => item.estado === paso.estado)
    let situacion = 'pendiente'
    if (indice < actual || estado === 'entregado') situacion = 'hecho'
    else if (indice === actual) situacion = 'actual'
    return { ...paso, situacion, fecha: registro?.fecha_hora ?? null }
  })
}

// Applies a WebSocket event (backend/pedidos/signals.py) to the order on screen
export function aplicarEvento(seguimiento, evento) {
  if (evento.tipo !== 'estado_pedido_cambiado' || evento.estado === seguimiento.estado) return seguimiento
  return {
    ...seguimiento,
    estado: evento.estado,
    estado_nombre: evento.estado_nombre,
    motivo_cancelacion: evento.motivo_cancelacion ?? seguimiento.motivo_cancelacion,
    historial: [
      ...seguimiento.historial,
      { estado: evento.estado, estado_nombre: evento.estado_nombre, fecha_hora: evento.fecha_hora },
    ],
  }
}

// HU-25: the customer can cancel only before the kitchen starts the order.
// Uses the current state (WebSocket events keep it fresh); the backend checks again
const CANCELABLES = ['pendiente_aprobacion', 'recibido']

export function puedeCancelar(estado) {
  if (CANCELABLES.includes(estado)) return { puede: true, motivo: null }
  if (estado === 'cancelado' || estado === 'entregado') return { puede: false, motivo: null }
  return {
    puede: false,
    motivo: 'Ya no puedes cancelarlo: la cocina empezó a preparar tu pedido. Comunícate con la sede si necesitas ayuda.',
  }
}
