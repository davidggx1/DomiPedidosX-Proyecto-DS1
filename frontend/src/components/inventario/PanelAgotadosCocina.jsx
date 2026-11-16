import { Link } from 'react-router-dom'
import { useAlertasInventario } from '../../alertas/useAlertasInventario.js'
import { horaExacta } from '../../utils/tiempo.js'

// HU-17 · Products the kitchen reported as sold out that are still unavailable.
// It is loaded when the page opens, so the operator sees them even if he was not
// connected when the popup arrived. Each one leaves the list when it is enabled again
export default function PanelAgotadosCocina() {
  const { agotados, disponible } = useAlertasInventario()
  if (!disponible || agotados.length === 0) return null

  return (
    <section
      role="status"
      aria-label="Agotados reportados por cocina"
      className="rounded-lg border border-error bg-superficie px-4 py-3"
    >
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 className="font-semibold text-error">✕ Agotados reportados por cocina ({agotados.length})</h2>
        <Link to="/operador/productos" className="text-sm font-medium text-marca-clara underline">
          Habilitar en Productos → Disponibilidad
        </Link>
      </div>
      <ul className="mt-2 divide-y divide-borde">
        {agotados.map((reporte) => (
          <li key={reporte.id} className="flex flex-wrap items-baseline justify-between gap-2 py-2">
            <span className="font-medium">{reporte.producto_nombre}</span>
            <span className="text-sm text-texto-suave">
              Reportado por {reporte.usuario_nombre} · {horaExacta(reporte.fecha_hora)}
            </span>
          </li>
        ))}
      </ul>
    </section>
  )
}
