// HU-26 · Textos del botón "Repetir pedido".

export const ESTADOS_REPETIBLES = ['entregado', 'cancelado']

export function puedeRepetirse(pedido) {
  return ESTADOS_REPETIBLES.includes(pedido.estado)
}

function unidades(lineas) {
  return lineas.reduce((total, linea) => total + linea.cantidad, 0)
}

// Aviso que se muestra después de pedir las líneas al backend.
// { tipo, titulo, faltantes: [{ nombre, motivo }], hayLineas }
export function avisoRepetir(numeroPedido, respuesta) {
  const { lineas, no_disponibles: faltantes, sede } = respuesta
  if (lineas.length === 0) {
    return {
      tipo: 'aviso',
      titulo: `Ningún producto del pedido ${numeroPedido} está disponible hoy en ${sede.nombre}.`,
      faltantes,
      hayLineas: false,
    }
  }
  const n = unidades(lineas)
  return {
    tipo: faltantes.length ? 'aviso' : 'exito',
    titulo: `Cargamos ${n} ${n === 1 ? 'producto' : 'productos'} del pedido ${numeroPedido} en tu carrito, con los precios de hoy.`,
    faltantes,
    hayLineas: true,
  }
}
