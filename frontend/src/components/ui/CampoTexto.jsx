import { useId, useRef } from 'react'

export default function CampoTexto({
  etiqueta,
  error,
  ayuda,
  requerido = false,
  id,
  className = '',
  tipo = 'text',
  type,
  onClick,
  ...props
}) {
  const inputRef = useRef(null)
  const idGenerado = useId()
  const idCampo = id ?? idGenerado
  const idAyuda = `${idCampo}-ayuda`
  const idError = `${idCampo}-error`
  const mostrarAyuda = ayuda && !error
  const descripcion = error ? idError : mostrarAyuda ? idAyuda : undefined

  // Permite recibir la prop como 'tipo' o como 'type'
  const tipoFinal = type || tipo

  const handleClick = (e) => {
    if (inputRef.current && (tipoFinal === 'date' || tipoFinal === 'time')) {
      if ('showPicker' in HTMLInputElement.prototype) {
        try {
          inputRef.current.showPicker()
        } catch {
          // Si el navegador bloquea showPicker por eventos
        }
      }
    }
    if (onClick) onClick(e)
  }

  return (
    <div className={`flex flex-col gap-1 ${className}`}>
      {etiqueta && (
        <label htmlFor={idCampo} className="text-sm font-medium">
          {etiqueta}
          {requerido && (
            <span className="text-marca-clara" aria-hidden="true">
              {' '}*
            </span>
          )}
        </label>
      )}
      <input
        ref={inputRef}
        id={idCampo}
        type={tipoFinal}
        onClick={handleClick}
        aria-required={requerido || undefined}
        aria-invalid={error ? true : undefined}
        aria-describedby={descripcion}
        className={`min-h-11 w-full rounded-lg border bg-fondo px-3 py-2 text-texto placeholder:text-texto-suave [color-scheme:dark] ${
          error ? 'border-error' : 'border-borde'
        } ${tipoFinal === 'date' || tipoFinal === 'time' ? 'cursor-pointer' : ''}`}
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