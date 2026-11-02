import { useId } from 'react'

// Casilla de verificación con su etiqueta. Usa checked y onChange como un <input>.
export default function Casilla({ etiqueta, descripcion, id, className = '', ...props }) {
  const idGenerado = useId()
  const idCampo = id ?? idGenerado
  const idDescripcion = `${idCampo}-descripcion`

  return (
    <div className={`flex items-start gap-3 ${className}`}>
      <input
        id={idCampo}
        type="checkbox"
        aria-describedby={descripcion ? idDescripcion : undefined}
        className="mt-1 h-5 w-5 shrink-0 accent-marca"
        {...props}
      />
      <div>
        <label htmlFor={idCampo} className="font-medium">
          {etiqueta}
        </label>
        {descripcion && (
          <p id={idDescripcion} className="text-sm text-texto-suave">
            {descripcion}
          </p>
        )}
      </div>
    </div>
  )
}
