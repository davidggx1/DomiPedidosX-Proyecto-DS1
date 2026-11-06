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
