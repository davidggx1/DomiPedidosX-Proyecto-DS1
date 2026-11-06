// Interruptor de encendido/apagado accesible (role="switch").
// El área tocable mide al menos 44 px de alto, como los botones.
export default function Interruptor({ activo, alCambiar, etiqueta, disabled = false, ocupado = false }) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={activo}
      aria-label={etiqueta}
      aria-busy={ocupado || undefined}
      disabled={disabled || ocupado}
      onClick={() => alCambiar(!activo)}
      className="inline-flex min-h-11 items-center rounded-full disabled:cursor-not-allowed disabled:opacity-50"
    >
      <span
        aria-hidden="true"
        className={`relative inline-flex h-6 w-11 items-center rounded-full border transition-colors ${
          activo ? 'border-exito bg-exito/30' : 'border-borde bg-superficie-alta'
        }`}
      >
        <span
          className={`inline-block size-4 rounded-full transition-transform ${
            activo ? 'translate-x-6 bg-exito' : 'translate-x-1 bg-texto-suave'
          }`}
        />
      </span>
    </button>
  )
}
