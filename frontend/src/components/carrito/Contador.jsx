// Botones − y + con el valor en medio. Se usa para cantidades y adiciones.
export default function Contador({ valor, minimo = 0, maximo = Infinity, alCambiar, etiqueta, disabled = false }) {
  const clasesBoton =
    'flex h-11 w-11 items-center justify-center rounded-lg border border-borde bg-superficie-alta text-lg font-bold hover:bg-borde disabled:cursor-not-allowed disabled:opacity-50'

  return (
    <div role="group" aria-label={etiqueta} className="flex items-center gap-2">
      <button
        type="button"
        className={clasesBoton}
        onClick={() => alCambiar(valor - 1)}
        disabled={disabled || valor <= minimo}
        aria-label={`Quitar uno: ${etiqueta}`}
      >
        −
      </button>
      <span aria-live="polite" className="min-w-8 text-center font-semibold">
        {valor}
      </span>
      <button
        type="button"
        className={clasesBoton}
        onClick={() => alCambiar(valor + 1)}
        disabled={disabled || valor >= maximo}
        aria-label={`Agregar uno: ${etiqueta}`}
      >
        +
      </button>
    </div>
  )
}
