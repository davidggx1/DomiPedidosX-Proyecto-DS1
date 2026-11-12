import { useAlertasInventario } from '../../alertas/useAlertasInventario.js'
import { textoStock } from '../../utils/alertasInventario.js'

// HU-16 · Items of the sede that reached their minimum stock. Each one leaves
// the list by itself when its stock goes over the minimum
export default function PanelStockBajo() {
  const { alertas, disponible } = useAlertasInventario()
  if (!disponible || alertas.length === 0) return null

  return (
    <section
      role="status"
      aria-label="Alertas de stock bajo"
      className="rounded-lg border border-aviso bg-superficie px-4 py-3"
    >
      <h2 className="font-semibold text-aviso">⚠ Stock bajo ({alertas.length})</h2>
      <ul className="mt-2 divide-y divide-borde">
        {alertas.map((alerta) => (
          <li key={alerta.id} className="flex flex-wrap items-baseline justify-between gap-2 py-2">
            <span className="font-medium">
              {alerta.nombre}
              <span className="text-xs font-normal text-texto-suave">
                {' '}
                · {alerta.tipo === 'producto' ? 'Producto' : 'Insumo'}
              </span>
            </span>
            <span className={`text-sm ${alerta.stock_actual === 0 ? 'text-error' : ''}`}>
              {textoStock(alerta)}
            </span>
          </li>
        ))}
      </ul>
    </section>
  )
}
