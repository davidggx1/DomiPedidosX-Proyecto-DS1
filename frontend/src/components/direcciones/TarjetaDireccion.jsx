import Boton from '../ui/Boton.jsx'

// Una dirección guardada en el listado, con sus acciones (HU-06).
export default function TarjetaDireccion({ direccion, alEditar, alEliminar }) {
  return (
    <li className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-borde bg-fondo px-3 py-2">
      <div className="min-w-0">
        <p className="font-medium">
          {direccion.alias}
          {direccion.es_principal && (
            <span className="ml-2 rounded-full bg-marca px-2 py-0.5 text-xs font-semibold text-sobre-marca">
              Principal
            </span>
          )}
        </p>
        <p className="text-sm break-words">{direccion.direccion}</p>
        {direccion.barrio && <p className="text-sm text-texto-suave">{direccion.barrio}</p>}
        {direccion.indicaciones && (
          <p className="text-sm break-words text-texto-suave">{direccion.indicaciones}</p>
        )}
      </div>
      <div className="flex gap-2">
        <Boton variante="secundario" onClick={alEditar} aria-label={`Editar ${direccion.alias}`}>
          Editar
        </Boton>
        <Boton variante="peligro" onClick={alEliminar} aria-label={`Eliminar ${direccion.alias}`}>
          Eliminar
        </Boton>
      </div>
    </li>
  )
}
