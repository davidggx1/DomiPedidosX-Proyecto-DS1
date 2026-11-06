import { datosEstado } from '../../utils/estadosPedido.js'
import { formatearPrecio } from '../../utils/formato.js'
import { horaCorta } from '../../utils/tiempo.js'

// Card of an order in progress in the list of the repartidor (HU-42)
export default function TarjetaEntrega({ entrega }) {
  const estado = datosEstado(entrega.estado)

  return (
    <li className="flex flex-col gap-2 rounded-xl border border-borde bg-fondo p-3">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <p className="font-bold">{entrega.numero_pedido}</p>
          <p className="text-sm text-texto-suave">Pedido a las {horaCorta(entrega.fecha_creacion)}</p>
        </div>
        <div className="flex flex-wrap gap-1">
          <span className={`rounded-full border px-2 py-0.5 text-xs font-medium ${estado.clases}`}>
            {estado.etiqueta}
          </span>
          {entrega.cobrar_en_efectivo && (
            <span className="rounded-full border border-aviso px-2 py-0.5 text-xs font-medium text-aviso">
              Cobrar en efectivo
            </span>
          )}
        </div>
      </div>

      <div className="text-sm">
        <p>{entrega.entrega_direccion || 'Sin dirección registrada'}</p>
        {entrega.entrega_barrio && <p className="text-texto-suave">{entrega.entrega_barrio}</p>}
      </div>

      <p className="text-sm">
        {entrega.cliente ? entrega.cliente.nombre : 'Cliente sin registrar'}
        {entrega.total && (
          <>
            {' · '}
            <span className="font-semibold">{formatearPrecio(entrega.total)}</span>
          </>
        )}
      </p>
    </li>
  )
}
