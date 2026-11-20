// Carrito del pedido que crea el operador (HU-24).
// Cada combinación producto + tamaño es una línea propia, con su precio.

// Mismo tope por ítem que el backend (ItemCarritoSerializer.cantidad)
export const MAXIMO_POR_LINEA = 50

export function claveLinea(productoId, tamanoId = null) {
  return `${productoId}-${tamanoId ?? 'base'}`
}

// Precio por unidad igual que el backend: precio base + adicional del tamaño.
export function precioConTamano(producto, tamano = null) {
  return Number(producto.precio_base) + (tamano ? Number(tamano.precio_adicional) : 0)
}

// true si la línea ya llegó al tope y no se le puede sumar otra unidad
export function lineaLlena(carrito, producto, tamano = null) {
  const clave = claveLinea(producto.id, tamano?.id)
  return (carrito.find((l) => l.clave === clave)?.cantidad ?? 0) >= MAXIMO_POR_LINEA
}

export function agregarLinea(carrito, producto, tamano = null) {
  const clave = claveLinea(producto.id, tamano?.id)
  if (lineaLlena(carrito, producto, tamano)) return carrito
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

// Cantidad válida para una línea: entero entre 1 y el tope; null si no es un número
export function normalizarCantidad(valor) {
  const numero = Math.trunc(Number(valor))
  if (!Number.isFinite(numero) || String(valor).trim() === '') return null
  return Math.min(Math.max(numero, 1), MAXIMO_POR_LINEA)
}

export function cambiarCantidad(carrito, clave, valor) {
  const cantidad = normalizarCantidad(valor)
  if (cantidad === null) return carrito
  return carrito.map((l) => (l.clave === clave ? { ...l, cantidad } : l))
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

// Primer texto de un error de DRF, que puede venir anidado: ["msg"], {"cantidad": ["msg"]}…
function primerTexto(valor) {
  if (valor == null) return null
  if (typeof valor === 'string') return valor
  const hijos = Array.isArray(valor) ? valor : Object.values(valor)
  for (const hijo of hijos) {
    const texto = primerTexto(hijo)
    if (texto) return texto
  }
  return null
}

const ERROR_GENERICO = 'Error al registrar el pedido.'

// "Hamburguesa: Solo quedan 2 unidades." en vez del JSON del 400.
// `carrito` da el nombre de la línea cuando el error solo trae su posición.
export function mensajeErrorPedido(datos, carrito = []) {
  if (!datos) return ERROR_GENERICO
  const { items } = datos

  // Validación de catálogo y stock: [{ indice, nombre, motivo }]
  if (Array.isArray(items) && items.some((e) => e?.motivo)) {
    return items.map((e) => (e.nombre ? `${e.nombre}: ${e.motivo}` : e.motivo)).join(' ')
  }

  // Validación de campos por ítem: { "0": { "cantidad": ["..."] } } o [{ ... }, {}]
  if (items && typeof items === 'object') {
    const mensajes = Object.entries(items)
      .map(([indice, error]) => {
        const texto = primerTexto(error)
        if (!texto) return null
        const nombre = carrito[Number(indice)]?.nombre
        return nombre ? `${nombre}: ${texto}` : texto
      })
      .filter(Boolean)
    if (mensajes.length > 0) return mensajes.join(' ')
  }

  return primerTexto(datos.detail) ?? primerTexto(datos) ?? ERROR_GENERICO
}
