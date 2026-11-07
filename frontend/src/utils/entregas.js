import { formatearPrecio } from './formato.js'

// What the repartidor must do with the money when he delivers (HU-43).
// tipo is the color of the banner: aviso when he has to charge, exito when it is paid
export function avisoDePago(entrega) {
  if (entrega.cobrar_en_efectivo) {
    return {
      tipo: 'aviso',
      titulo: `Cobrar ${formatearPrecio(entrega.total)} en efectivo`,
      texto: 'El cliente paga al recibir. Lleva cambio.',
    }
  }
  if (entrega.metodo_pago) {
    return {
      tipo: 'exito',
      titulo: `Pagado con ${entrega.metodo_pago_nombre.toLowerCase()}`,
      texto: 'No cobres nada al entregar.',
    }
  }
  return {
    tipo: 'info',
    titulo: 'Sin información de pago',
    texto: 'Confirma con el operador de la sede antes de cobrar.',
  }
}

// Google Maps link to the delivery address: by coordinates when the address has them (HU-06)
export function enlaceMapa(entrega) {
  const destino =
    entrega.entrega_latitud != null && entrega.entrega_longitud != null
      ? `${entrega.entrega_latitud},${entrega.entrega_longitud}`
      : [entrega.entrega_direccion, entrega.entrega_barrio, 'Cali'].filter(Boolean).join(', ')
  return `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(destino)}`
}

// The one step forward the repartidor gives from each state (HU-45), in strict order
export const AVANCE_ENTREGA = {
  listo_despacho: {
    estado: 'recogido',
    texto: 'Recogí el pedido',
    pregunta: '¿Ya recogiste el pedido en la sede?',
  },
  recogido: {
    estado: 'en_camino',
    texto: 'Voy en camino',
    pregunta: '¿Sales ahora hacia la dirección del cliente?',
  },
  en_camino: {
    estado: 'entregado',
    texto: 'Marcar como entregado',
    pregunta: '¿Ya le entregaste el pedido al cliente?',
  },
}

// The next step, only if the API says this repartidor can give it
export function avanceDeEntrega(entrega) {
  const avance = AVANCE_ENTREGA[entrega.estado]
  return avance && entrega.siguientes_estados.includes(avance.estado) ? avance : null
}

// Change to give back. null while the amount is empty or does not cover the total
export function calcularCambio(recibido, total) {
  if (recibido === '' || recibido == null) return null
  const monto = Number(recibido)
  if (!Number.isFinite(monto) || monto < Number(total)) return null
  return monto - Number(total)
}
