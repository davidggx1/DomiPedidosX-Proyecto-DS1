import { describirCapacidad } from '../../utils/capacidad.js'

// Colors by level: yellow from the umbral of the slot (HU-60), red at 100%
const ESTILOS = {
  normal: { caja: 'border-borde', titulo: 'text-texto', barra: 'bg-exito', icono: '' },
  alerta: { caja: 'border-aviso', titulo: 'text-aviso', barra: 'bg-aviso', icono: '⚠ ' },
  saturada: { caja: 'border-error', titulo: 'text-error', barra: 'bg-error', icono: '✕ ' },
  sin_franja: { caja: 'border-borde', titulo: 'text-texto-suave', barra: 'bg-borde', icono: '' },
}

// Capacity of the sede for the operator panel: one widget that always follows
// the last state received, so the alert is never shown twice
export default function EstadoCapacidadSede({ capacidad }) {
  const info = describirCapacidad(capacidad)
  if (!info) return null
  const estilo = ESTILOS[info.nivel]

  return (
    <section
      role="status"
      aria-label="Capacidad de la sede"
      className={`rounded-lg border bg-superficie px-4 py-3 ${estilo.caja}`}
    >
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <p className={`font-semibold ${estilo.titulo}`}>
          {estilo.icono}
          {info.titulo}
        </p>
        <p className="text-sm">{info.texto}</p>
      </div>

      {info.porcentaje !== null && (
        <div
          role="progressbar"
          aria-label="Ocupación de la franja"
          aria-valuemin={0}
          aria-valuemax={100}
          aria-valuenow={info.porcentaje}
          className="mt-2 h-2 w-full overflow-hidden rounded-full bg-fondo"
        >
          <div className={`h-full ${estilo.barra}`} style={{ width: `${info.porcentaje}%` }} />
        </div>
      )}
    </section>
  )
}
