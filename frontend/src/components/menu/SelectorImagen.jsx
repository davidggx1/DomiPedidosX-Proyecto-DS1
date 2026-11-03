import { useEffect, useId, useMemo, useRef } from 'react'

const TIPOS_IMAGEN = ['image/jpeg', 'image/png']
const TAMANO_MAX_IMAGEN = 2 * 1024 * 1024 // 2 MB, igual que el backend

// Mismas reglas que el backend: solo JPG o PNG de máximo 2 MB.
function validarImagen(archivo) {
  if (!TIPOS_IMAGEN.includes(archivo.type)) return 'Formato no permitido. Usa JPG o PNG.'
  if (archivo.size > TAMANO_MAX_IMAGEN) return 'La imagen no puede superar 2 MB.'
  return null
}

// Campo para elegir la foto del producto con vista previa (HU-11).
// `archivo` es el File elegido; `imagenActual` es la URL que ya tiene el producto.
export default function SelectorImagen({ archivo, imagenActual, error, alCambiar, nombreProducto }) {
  const idCampo = useId()
  const idDescripcion = `${idCampo}-descripcion`
  const campo = useRef(null)

  const vistaPrevia = useMemo(() => (archivo ? URL.createObjectURL(archivo) : null), [archivo])

  // Libera la URL temporal cuando cambia el archivo o se cierra el formulario.
  useEffect(() => {
    if (!vistaPrevia) return undefined
    return () => URL.revokeObjectURL(vistaPrevia)
  }, [vistaPrevia])

  const imagen = vistaPrevia ?? imagenActual

  function elegir(evento) {
    const elegido = evento.target.files?.[0]
    if (!elegido) return
    const problema = validarImagen(elegido)
    if (problema) {
      // Se limpia para que se pueda volver a elegir el mismo archivo después de corregirlo.
      evento.target.value = ''
      alCambiar(null, problema)
      return
    }
    alCambiar(elegido, null)
  }

  function descartar() {
    if (campo.current) campo.current.value = ''
    alCambiar(null, null)
  }

  return (
    <div className="flex flex-col gap-2">
      <label htmlFor={idCampo} className="text-sm font-medium">
        Foto del producto
      </label>

      <div className="flex flex-col gap-3 sm:flex-row sm:items-start">
        <div className="aspect-video w-full overflow-hidden rounded-lg border border-borde bg-superficie-alta sm:w-48 sm:shrink-0">
          {imagen ? (
            <img
              src={imagen}
              alt={vistaPrevia ? 'Vista previa de la foto elegida' : `Foto actual de ${nombreProducto || 'el producto'}`}
              className="h-full w-full object-cover"
            />
          ) : (
            <p className="flex h-full items-center justify-center p-2 text-center text-sm text-texto-suave">
              Sin foto
            </p>
          )}
        </div>

        <div className="flex flex-col gap-2">
          <input
            ref={campo}
            id={idCampo}
            type="file"
            accept="image/jpeg,image/png"
            onChange={elegir}
            aria-invalid={error ? true : undefined}
            aria-describedby={idDescripcion}
            className="text-sm text-texto file:mr-3 file:min-h-11 file:cursor-pointer file:rounded-lg file:border file:border-borde file:bg-superficie-alta file:px-4 file:py-2 file:font-medium file:text-texto hover:file:bg-borde"
          />
          <p id={idDescripcion} className={`text-sm ${error ? 'text-error' : 'text-texto-suave'}`}>
            {error ?? 'JPG o PNG, máximo 2 MB. Es opcional.'}
          </p>
          {archivo && (
            <button
              type="button"
              onClick={descartar}
              className="self-start text-sm text-texto-suave underline hover:text-texto"
            >
              {imagenActual ? 'Conservar la foto actual' : 'Quitar la foto elegida'}
            </button>
          )}
        </div>
      </div>
    </div>
  )
}
