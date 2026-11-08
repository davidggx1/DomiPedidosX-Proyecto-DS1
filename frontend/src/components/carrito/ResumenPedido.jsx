import { useCarrito } from '../context/useCarrito.js'

export function ResumenPedido({ onConfirmar }) {
  const {subtotal, costoDomicilio, total, articulos } = useCarrito()

  const formatearMoneda = (valor) =>
    new Intl.NumberFormat('es-CO', {
      style: 'currency',
      currency: 'COP',
      maximumFractionDigits: 0,
    }).format(valor)

  if (articulos === 0) {
    return (
      <div className="p-4 text-center text-gray-500 border rounded-lg bg-gray-50">
        El carrito está vacío.
      </div>
    )
  }

  return (
    <div className="p-5 border rounded-xl bg-white shadow-sm space-y-4">
      <h3 className="text-lg font-bold text-gray-800 border-b pb-2">Resumen de Compra</h3>

      <div className="space-y-2 text-sm text-gray-600">
        <div className="flex justify-between">
          <span>Subtotal ({articulos} ítems):</span>
          <span className="font-semibold text-gray-800">{formatearMoneda(subtotal)}</span>
        </div>

        <div className="flex justify-between">
          <span>Costo de Domicilio:</span>
          <span className="font-semibold text-gray-800">{formatearMoneda(costoDomicilio)}</span>
        </div>

        <div className="border-t pt-3 flex justify-between text-base font-bold text-gray-900">
          <span>Total a Pagar:</span>
          <span className="text-amber-800">{formatearMoneda(total)}</span>
        </div>
      </div>

      <button
        onClick={onConfirmar}
        className="w-full mt-4 bg-amber-800 hover:bg-amber-900 text-white font-bold py-2.5 px-4 rounded-lg transition-colors"
      >
        Confirmar Pedido
      </button>
    </div>
  )
}