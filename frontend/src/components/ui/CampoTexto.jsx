import { useId } from 'react'

// Campo de texto con etiqueta, texto de ayuda y mensaje de error accesibles.
// Cualquier prop extra (type, value, onChange, placeholder...) pasa al <input>.
export default function CampoTexto({
  etiqueta,
  error,
  ayuda,
  requerido = false,
  id,
  className = '',
  ...props
}) {
  const idGenerado = useId()
  const idCampo = id ?? idGenerado
  const idAyuda = `${idCampo}-ayuda`
  const idError = `${idCampo}-error`
  const mostrarAyuda = ayuda && !error
  const descripcion = error ? idError : mostrarAyuda ? idAyuda : undefined

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
      <input
        id={idCampo}
        aria-required={requerido || undefined}
        aria-invalid={error ? true : undefined}
        aria-describedby={descripcion}
        className={`min-h-11 rounded-lg border bg-fondo px-3 py-2 text-texto placeholder:text-texto-suave ${error ? 'border-error' : 'border-borde'}`}
        {...props}
      />
      {mostrarAyuda && (
        <p id={idAyuda} className="text-sm text-texto-suave">
          {ayuda}
        </p>
      )}
      {error && (
        <p id={idError} className="text-sm text-error">
          {error}
        </p>
      )}
    </div>
  )
}
