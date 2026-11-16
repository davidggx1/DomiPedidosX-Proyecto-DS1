// HU-62: alternate sede when the sede of the customer is blocked
import { quitarLineasRetiradas } from './carrito.js'

// The checkout offers a way out when the sede is saturated or has no slot (HU-61)
export function ofreceAlternativas(estadoCapacidad) {
  if (!estadoCapacidad) return false
  if (estadoCapacidad.estado === 'saturada') return true
  return estadoCapacidad.estado === 'sin_franja' && Boolean(estadoCapacidad.bloqueado)
}

// Ids of the products of the cart, without repeats
export function idsDeProductos(lineas) {
  return [...new Set(lineas.map((linea) => linea.producto.id))]
}

export function textoDistancia(km) {
  return `${String(km).replace('.', ',')} km`
}

function listaConY(nombres) {
  const entreComillas = nombres.map((nombre) => `"${nombre}"`)
  if (entreComillas.length === 1) return entreComillas[0]
  const ultimo = entreComillas.pop()
  return `${entreComillas.join(', ')} y ${ultimo}`
}

// What the other sede does not have of the cart, or null if it has everything
export function textoNoDisponibles(alternativa) {
  const lista = alternativa.no_disponibles ?? []
  if (lista.length === 0) return null
  const nombres = [...new Set(lista.map((producto) => producto.nombre ?? 'un producto'))]
  const verbo = nombres.length === 1 ? 'no está disponible' : 'no están disponibles'
  return `${listaConY(nombres)} ${verbo} en esta sede y se quitará de tu carrito.`
}

// Moves the cart to the new sede: the lines of the products it does not have are removed.
// Prices are the same in every sede, availability is what changes
export function trasladarCarrito(lineas, alternativa) {
  const noDisponibles = (alternativa.no_disponibles ?? []).map((producto) => producto.id)
  return quitarLineasRetiradas(lineas, noDisponibles)
}

// Same shape the checkout gets from validar-cobertura, so the delivery fee, the minimum
// and the distance shown are the ones of the new sede
export function coberturaDeAlternativa(alternativa) {
  return {
    cubierto: true,
    mensaje: `Dirección con cobertura confirmada para ${alternativa.sede.nombre}.`,
    sede: {
      id: alternativa.sede.id,
      nombre: alternativa.sede.nombre,
      direccion: alternativa.sede.direccion,
      distancia_km: alternativa.distancia_km,
      tarifa_domicilio: alternativa.tarifa_domicilio,
      pedido_minimo: alternativa.pedido_minimo,
      tiempo_estimado: alternativa.tiempo_estimado,
    },
  }
}

// Notice after the customer accepts the change
export function textoCambioDeSede(alternativa, quitadas) {
  const base = `Cambiaste a la sede ${alternativa.sede.nombre}. El domicilio, el pedido mínimo y el tiempo de entrega ahora son los de esa sede.`
  const nombres = [...new Set(quitadas.map((linea) => linea.producto.nombre))]
  if (nombres.length === 0) return base
  const verbo = nombres.length === 1 ? 'no está disponible allí y se quitó' : 'no están disponibles allí y se quitaron'
  return `${base} ${listaConY(nombres)} ${verbo} de tu carrito.`
}
