import Boton from '../ui/Boton.jsx'
import { formatearPrecio } from '../../utils/formato.js'

// Tarjeta de producto del menú del cliente (se reutiliza en HU-18).
// Si el producto no está disponible, muestra la etiqueta y bloquea el botón.
export default function TarjetaProducto({ producto, alAgregar }) {
  const { nombre, precio, imagen, disponible } = producto

  return (
    <article className="flex flex-col gap-3 rounded-xl border border-borde bg-superficie p-4">
      {imagen ? (
        <img
          src={imagen}
          alt={`Foto de ${nombre}`}
          className="aspect-video w-full rounded-lg object-cover"
        />
      ) : (
        <div aria-hidden="true" className="aspect-video w-full rounded-lg bg-superficie-alta" />
      )}

      <div className="flex items-start justify-between gap-2">
        <h3 className="font-bold">{nombre}</h3>
        {!disponible && (
          <span className="shrink-0 rounded-full border border-aviso px-2 py-0.5 text-xs font-medium text-aviso">
            No disponible
          </span>
        )}
      </div>

      <p className="text-lg">{formatearPrecio(precio)}</p>

      <Boton
        onClick={() => alAgregar?.(producto)}
        disabled={!disponible}
        aria-label={disponible ? `Agregar ${nombre} al carrito` : `${nombre} no está disponible`}
        className="mt-auto self-start"
      >
        Agregar
      </Boton>
    </article>
  )
}
