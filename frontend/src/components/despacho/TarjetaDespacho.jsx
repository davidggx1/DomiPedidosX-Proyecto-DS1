import { useState } from 'react'
import { minutosEntre, textoDuracion } from '../../utils/tiempo.js'
import Boton from '../ui/Boton.jsx'
import Selector from '../ui/Selector.jsx'

// Order waiting for a repartidor. It assigns one from the free list or takes the assignment back (HU-35)
export default function TarjetaDespacho({ pedido, libres, ahora, ocupado, alAsignar, alRetirar }) {
  const [elegido, setElegido] = useState('')
  const [error, setError] = useState(null)

  const opciones = libres.map((repartidor) => ({
    valor: String(repartidor.id),
    etiqueta: `${repartidor.nombres} ${repartidor.apellidos}`,
  }))

  function asignar() {
    if (!elegido) {
      setError('Selecciona un repartidor.')
      return
    }
    setError(null)
    alAsignar(pedido, Number(elegido))
  }

  return (
    <li className="flex flex-col gap-3 rounded-xl border border-borde bg-fondo p-3">
      <div>
        <p className="font-bold">{pedido.numero_pedido}</p>
        <p className="text-sm text-texto-suave">
          Listo hace {textoDuracion(minutosEntre(pedido.listo_en, ahora))}
        </p>
        {pedido.entrega_direccion && (
          <p className="text-sm">
            {pedido.entrega_direccion}
            {pedido.entrega_barrio && <span className="text-texto-suave"> · {pedido.entrega_barrio}</span>}
          </p>
        )}
      </div>

      <ul className="flex flex-col gap-1 text-sm">
        {pedido.resumen.map((linea, indice) => (
          <li key={`${linea}-${indice}`}>{linea}</li>
        ))}
      </ul>

      {pedido.repartidor ? (
        <div className="flex flex-wrap items-center justify-between gap-3 border-t border-borde pt-3">
          <p>
            Repartidor: <strong>{pedido.repartidor.nombre}</strong>
          </p>
          <Boton
            variante="peligro"
            onClick={() => alRetirar(pedido)}
            cargando={ocupado}
            aria-label={`Quitar la asignación del pedido ${pedido.numero_pedido}`}
          >
            Quitar asignación
          </Boton>
        </div>
      ) : (
        <div className="flex flex-col gap-3 border-t border-borde pt-3">
          <Selector
            etiqueta="Repartidor"
            name={`repartidor-${pedido.id}`}
            opciones={opciones}
            value={elegido}
            onChange={(evento) => setElegido(evento.target.value)}
            error={error}
            textoVacio={opciones.length === 0 ? 'No hay repartidores libres' : 'Selecciona un repartidor'}
            disabled={opciones.length === 0 || ocupado}
          />
          <div>
            <Boton
              onClick={asignar}
              cargando={ocupado}
              disabled={opciones.length === 0}
              aria-label={`Asignar repartidor al pedido ${pedido.numero_pedido}`}
            >
              Asignar
            </Boton>
          </div>
        </div>
      )}
    </li>
  )
}
