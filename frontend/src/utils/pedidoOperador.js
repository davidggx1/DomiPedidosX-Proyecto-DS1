// Carrito del pedido que crea el operador (HU-24).
// Cada combinación producto + tamaño es una línea propia, con su precio.

export function claveLinea(productoId, tamanoId = null) {
  return `${productoId}-${tamanoId ?? 'base'}`
}

// Precio por unidad igual que el backend: precio base + adicional del tamaño.
export function precioConTamano(producto, tamano = null) {
  return Number(producto.precio_base) + (tamano ? Number(tamano.precio_adicional) : 0)
}

export function agregarLinea(carrito, producto, tamano = null) {
  const clave = claveLinea(producto.id, tamano?.id)
  if (carrito.some((l) => l.clave === clave)) {
    return carrito.map((l) => (l.clave === clave ? { ...l, cantidad: l.cantidad + 1 } : l))
  }
  return [
    ...carrito,
    {
      clave,
      producto_id: producto.id,
      tamano_id: tamano?.id ?? null,
      nombre: tamano ? `${producto.nombre} (${tamano.nombre})` : producto.nombre,
      precio: precioConTamano(producto, tamano),
      cantidad: 1,
    },
  ]
}

export function quitarLinea(carrito, clave) {
  return carrito.filter((l) => l.clave !== clave)
}

export function itemsParaEnviar(carrito) {
  return carrito.map((l) => ({
    producto_id: l.producto_id,
    ...(l.tamano_id && { tamano_id: l.tamano_id }),
    cantidad: l.cantidad,
    adiciones: [],
    exclusiones: [],
    observaciones: '',
  }))
}

// "Hamburguesa: Solo quedan 2 unidades." en vez del JSON del 400.
export function mensajeErrorPedido(datos) {
  if (!datos) return 'Error al registrar el pedido.'
  if (Array.isArray(datos.items) && datos.items.length > 0) {
    return datos.items
      .map((e) => (e.nombre ? `${e.nombre}: ${e.motivo}` : e.motivo))
      .join(' ')
  }
  if (typeof datos.detail === 'string') return datos.detail
  const primero = Object.values(datos)[0]
  return Array.isArray(primero) ? String(primero[0]) : String(primero ?? 'Error al registrar el pedido.')
}
