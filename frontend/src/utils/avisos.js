// HU-40 · Convierte un mensaje del WebSocket del repartidor en un aviso para la pantalla.
// Devuelve null si el mensaje no trae aviso (cambios silenciosos, p. ej. él mismo avanzó la entrega).
export function avisoDeMensaje(datos, id = Date.now()) {
  const aviso = datos?.aviso
  if (!aviso) return null

  if (aviso.tipo === 'asignado') {
    return {
      id,
      tipo: 'asignado',
      titulo: `Nuevo pedido: ${aviso.numero_pedido}`,
      texto: aviso.mensaje,
      // criterio 2: tocar el aviso abre el detalle con la dirección
      enlace: `/repartidor/entregas/${datos.pedido_id}`,
    }
  }

  return {
    id,
    tipo: 'retirado',
    titulo: aviso.motivo === 'cancelado' ? `Pedido ${aviso.numero_pedido} cancelado` : `Pedido ${aviso.numero_pedido} retirado`,
    texto: aviso.mensaje,
    enlace: null,
  }
}

// Cuánto se queda el aviso en pantalla. El de asignación dura más: es el que importa no perder
export function duracionAviso(aviso) {
  return aviso.tipo === 'asignado' ? 30000 : 10000
}
