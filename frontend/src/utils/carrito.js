// HU-21 · Lógica del carrito sin React, para poder probarla con Vitest.
//
// Una línea del carrito:
// {
//   id, producto: { id, nombre, imagen, precio_base },
//   tamano: { id, nombre, precio_adicional } | null,
//   adiciones: [{ adicion, nombre, precio, cantidad }],
//   exclusiones: [{ id, nombre }],   // id del ingrediente (ProductoInsumo) que se quita
//   cantidad, precio_unitario,       // precio_unitario lo confirma el backend
// }
// Los precios llegan del backend como texto ("20000.00"); aquí se suman como números.

// Cada cliente tiene su propio carrito en el navegador. Sin cliente no hay carrito.
export function claveCarrito(usuario) {
  if (usuario?.rol !== 'cliente' || !usuario.email) return null
  return `domipedidosx.carrito.${usuario.email.toLowerCase()}`
}

// Precio de una unidad: base + tamaño + Σ(adición × cantidad). Sirve para la vista previa.
export function precioUnitario({ producto, tamano, adiciones = [] }) {
  const base = Number(producto.precio_base) + Number(tamano?.precio_adicional ?? 0)
  return adiciones.reduce((total, item) => total + Number(item.precio) * item.cantidad, base)
}

export function subtotalLinea(linea) {
  return Number(linea.precio_unitario) * linea.cantidad
}

export function subtotalCarrito(lineas) {
  return lineas.reduce((total, linea) => total + subtotalLinea(linea), 0)
}

export function cantidadArticulos(lineas) {
  return lineas.reduce((total, linea) => total + linea.cantidad, 0)
}

// Identifica la configuración de una línea, sin importar el orden de las adiciones
// o exclusiones. Dos líneas con la misma clave son la misma variante del producto.
export function claveVariante({ producto, tamano, adiciones = [], exclusiones = [] }) {
  const partesAdiciones = adiciones
    .filter((item) => item.cantidad > 0)
    .map((item) => `${item.adicion}x${item.cantidad}`)
    .sort()
  const partesExclusiones = exclusiones.map((item) => String(item.id)).sort()
  return [
    producto.id,
    tamano?.id ?? '-',
    partesAdiciones.join(',') || '-',
    partesExclusiones.join(',') || '-',
  ].join('|')
}

// Línea con la misma configuración que `linea` (sin contar la línea `excluirId`).
export function buscarLineaIgual(lineas, linea, excluirId = null) {
  const clave = claveVariante(linea)
  return lineas.find((otra) => otra.id !== excluirId && claveVariante(otra) === clave) ?? null
}

// Si ya existe la misma variante se suma la cantidad; si no, entra como línea nueva.
export function agregarLinea(lineas, nueva) {
  const igual = buscarLineaIgual(lineas, nueva)
  if (!igual) return [...lineas, nueva]
  return lineas.map((linea) =>
    linea.id === igual.id
      ? { ...linea, cantidad: linea.cantidad + nueva.cantidad, precio_unitario: nueva.precio_unitario }
      : linea,
  )
}

// Edición de una línea. Si queda igual a otra línea, se fusionan en esa otra.
export function reemplazarLinea(lineas, id, nueva) {
  const sinLaAnterior = lineas.filter((linea) => linea.id !== id)
  if (buscarLineaIgual(sinLaAnterior, nueva)) return agregarLinea(sinLaAnterior, nueva)
  return lineas.map((linea) => (linea.id === id ? { ...nueva, id } : linea))
}

export function actualizarCantidad(lineas, id, cantidad) {
  if (cantidad < 1) return eliminarLinea(lineas, id)
  return lineas.map((linea) => (linea.id === id ? { ...linea, cantidad } : linea))
}

export function eliminarLinea(lineas, id) {
  return lineas.filter((linea) => linea.id !== id)
}

// Una adición y un ingrediente base con el mismo insumo se excluyen entre sí:
// no se puede quitar el queso y agregar queso extra a la vez.
// ingredientes y adiciones vienen del detalle del producto (HU-20);
// cantidades = { [adicion]: n } y exclusiones = Set de ids de ingrediente.
// Devuelve qué opción bloquea a cuál: { adiciones: { [adicion]: ingrediente }, ingredientes: { [id]: adicion } }.
export function bloqueosPorInsumo({ ingredientes, adiciones, cantidades, exclusiones }) {
  const bloqueos = { adiciones: {}, ingredientes: {} }
  for (const ingrediente of ingredientes) {
    for (const adicion of adiciones) {
      if (ingrediente.insumo !== adicion.insumo) continue
      if (exclusiones.has(ingrediente.id)) bloqueos.adiciones[adicion.adicion] = ingrediente
      if ((cantidades[adicion.adicion] ?? 0) > 0) bloqueos.ingredientes[ingrediente.id] = adicion
    }
  }
  return bloqueos
}

// Datos que espera POST /api/menu/sedes/<id>/carrito/linea/.
export function lineaParaValidar(linea) {
  return {
    producto: linea.producto.id,
    tamano: linea.tamano?.id ?? null,
    adiciones: linea.adiciones
      .filter((item) => item.cantidad > 0)
      .map((item) => ({ adicion: item.adicion, cantidad: item.cantidad })),
    exclusiones: linea.exclusiones.map((item) => item.id),
    cantidad: linea.cantidad,
  }
}

// Tarifa fija provisional por sede para el PMV (Sprint 2) - HU-22
export const TARIFA_DOMICILIO_PROVISIONAL_DEFAULT = 4000

/**
 * Calcula el costo de domicilio provisional de la sede (HU-22).
 * Si el carrito está vacío (subtotal = 0), el domicilio no se cobra.
 */
export function domicilioCarrito(subtotal, tarifaSede = TARIFA_DOMICILIO_PROVISIONAL_DEFAULT) {
  return subtotal > 0 ? tarifaSede : 0
}

/**
 * Calcula el total definitivo a pagar: Subtotal + Domicilio (HU-22).
 */
export function totalCarrito(subtotal, domicilio) {
  return subtotal + domicilio
}

/**
 * Domicilio con la tarifa REAL de la zona de la dirección (HU-22).
 * Si la zona aún no se conoce (tarifa null o undefined) devuelve null: no se inventa un valor.
 */
export function domicilioDeZona(subtotal, tarifaZona) {
  if (tarifaZona == null) return null
  return domicilioCarrito(subtotal, Number(tarifaZona))
}