// Etiqueta con texto y símbolo, para que no dependa solo del color
function Etiqueta({ tipo, children }) {
  const clases =
    tipo === 'adicion'
      ? 'border-exito bg-exito/15 text-exito'
      : 'border-error bg-error/15 text-error'
  return (
    <span className={`rounded-full border px-2 py-0.5 text-sm font-medium ${clases}`}>
      {children}
    </span>
  )
}

// Nota del cliente, destacada para que cocina no la pase por alto (HU-30)
function Nota({ children }) {
  return (
    <p className="rounded-lg border border-aviso bg-aviso/15 px-3 py-2 text-sm">
      <strong className="text-aviso">Nota del cliente: </strong>
      {children}
    </p>
  )
}

// What cocina needs to prepare an order: additions in green, removed ingredients in red and notes
export default function DetalleComanda({ comanda }) {
  return (
    <div className="flex flex-col gap-3">
      {comanda.notas?.trim() && <Nota>{comanda.notas}</Nota>}

      <ul className="flex flex-col gap-3">
        {comanda.lineas.map((linea) => (
          <li key={linea.id} className="flex flex-col gap-2 rounded-lg border border-borde bg-fondo p-3">
            <p className="font-medium">
              {linea.cantidad}x {linea.nombre}
              {linea.tamano && <span className="text-texto-suave"> ({linea.tamano})</span>}
            </p>

            {(linea.adiciones.length > 0 || linea.sin.length > 0) && (
              <div className="flex flex-wrap gap-2">
                {linea.adiciones.map((adicion) => (
                  <Etiqueta key={adicion.nombre} tipo="adicion">
                    + {adicion.nombre}
                    {adicion.cantidad > 1 && ` x${adicion.cantidad}`}
                  </Etiqueta>
                ))}
                {linea.sin.map((ingrediente) => (
                  <Etiqueta key={ingrediente} tipo="sin">
                    Sin {ingrediente}
                  </Etiqueta>
                ))}
              </div>
            )}

            {linea.observaciones?.trim() && <Nota>{linea.observaciones}</Nota>}
          </li>
        ))}
      </ul>
    </div>
  )
}
