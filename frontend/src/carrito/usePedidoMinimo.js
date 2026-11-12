import { useZonaEntrega } from './useZonaEntrega.js'

// Se conserva por compatibilidad: devuelve solo el pedido mínimo (HU-57).
// Para el carrito y el checkout usa useZonaEntrega, que además trae la tarifa de domicilio.
export function usePedidoMinimo() {
  return useZonaEntrega().pedidoMinimo
}