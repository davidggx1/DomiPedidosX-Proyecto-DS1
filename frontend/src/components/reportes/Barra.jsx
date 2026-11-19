import { anchoBarra } from '../../utils/reportes.js'

// Barra horizontal de una sola serie: el valor va escrito al lado, el color solo acompaña
export default function Barra({ etiqueta, valor, maximo, texto }) {
  return (
    <div
      className="h-2.5 overflow-hidden rounded-full bg-superficie-alta"
      role="img"
      aria-label={`${etiqueta}: ${texto}`}
      title={`${etiqueta}: ${texto}`}
    >
      <div className="h-full rounded-full bg-marca" style={{ width: `${anchoBarra(valor, maximo)}%` }} />
    </div>
  )
}
