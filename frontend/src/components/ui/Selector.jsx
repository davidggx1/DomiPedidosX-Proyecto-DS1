import { useId } from 'react'

// Lista desplegable. opciones = [{ valor: '1', etiqueta: 'Sede Centro' }, ...]
export default function Selector({
  etiqueta,
  opciones,
  error,
  requerido = false,
  textoVacio = 'Selecciona una opción',
  id,
  className = '',
  ...props
}) {
  const idGenerado = useId()
  const idCampo = id ?? idGenerado
  const idError = `${idCampo}-error`

  return (
    <div className={`flex flex-col gap-1 ${className}`}>
      <label htmlFor={idCampo} className="text-sm font-medium">
        {etiqueta}
        {requerido && (
          <span className="text-marca-clara" aria-hidden="true">
            {' '}*
          </span>
        )}
      </label>
      <select
        id={idCampo}
        aria-required={requerido || undefined}
        aria-invalid={error ? true : undefined}
        aria-describedby={error ? idError : undefined}
        className={`min-h-11 rounded-xl border bg-fondo px-3 py-2 text-texto ${error ? 'border-error' : 'border-borde'}`}
        {...props}
      >
        <option value="">{textoVacio}</option>
        {opciones.map((opcion) => (
          <option key={opcion.valor} value={opcion.valor}>
            {opcion.etiqueta}
          </option>
        ))}
      </select>
      {error && (
        <p id={idError} className="text-sm text-error">
          {error}
        </p>
      )}
    </div>
  )
}
