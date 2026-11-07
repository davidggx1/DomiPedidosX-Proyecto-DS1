import { horaCorta } from '../../utils/tiempo.js'

const ESTILO_PUNTO = {
  hecho: 'border-exito bg-exito text-fondo',
  actual: 'border-marca-clara bg-marca text-white ring-4 ring-marca/30',
  pendiente: 'border-borde bg-superficie text-texto-suave',
}

// HU-47 · Progress bar of the order: done steps with their time, the current one
// highlighted and the next ones grey. Vertical on phones, horizontal on wide screens
export default function BarraProgresoPedido({ pasos }) {
  return (
    <ol className="flex flex-col gap-4 md:grid md:grid-cols-7 md:gap-2">
      {pasos.map((paso, indice) => (
        <li
          key={paso.estado}
          aria-current={paso.situacion === 'actual' ? 'step' : undefined}
          className="flex gap-3 md:flex-col md:items-center md:text-center"
        >
          <span
            aria-hidden="true"
            className={`flex size-8 shrink-0 items-center justify-center rounded-full border-2 text-sm font-bold ${ESTILO_PUNTO[paso.situacion]}`}
          >
            {paso.situacion === 'hecho' ? '✓' : indice + 1}
          </span>
          <div className="flex flex-col">
            <span className={paso.situacion === 'pendiente' ? 'text-texto-suave' : 'font-semibold'}>
              {paso.titulo}
              <span className="sr-only">
                {paso.situacion === 'hecho' ? ' (completado)' : paso.situacion === 'actual' ? ' (paso actual)' : ''}
              </span>
            </span>
            {paso.fecha && <span className="text-xs text-texto-suave">{horaCorta(paso.fecha)}</span>}
            {paso.situacion === 'actual' && <span className="text-sm text-texto-suave md:hidden">{paso.texto}</span>}
          </div>
        </li>
      ))}
    </ol>
  )
}
