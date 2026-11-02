const formatoPesos = new Intl.NumberFormat('es-CO', {
  style: 'currency',
  currency: 'COP',
  maximumFractionDigits: 0,
})

// 18000 -> "$ 18.000". Acepta números o textos (el backend envía decimales como texto).
export function formatearPrecio(valor) {
  return formatoPesos.format(Number(valor))
}
