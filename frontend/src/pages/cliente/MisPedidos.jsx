import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { interpretarError } from '../../api/errores.js'
import { listarMisPedidos } from '../../api/pedidos.js'
import Alerta from '../../components/ui/Alerta.jsx'
import Tarjeta from '../../components/ui/Tarjeta.jsx'
import { datosEstado } from '../../utils/estadosPedido.js'
import { formatearPrecio } from '../../utils/formato.js'
import { horaCorta } from '../../utils/tiempo.js'

const CERRADOS = ['entregado', 'cancelado']

function TarjetaPedidoCliente({ pedido }) {
  const estado = datosEstado(pedido.estado)
  const fecha = new Date(pedido.fecha_creacion).toLocaleDateString('es-CO', { day: 'numeric', month: 'short' })
  return (
    <li>
      <Link
        to={`/mis-pedidos/${pedido.id}`}
        aria-label={`Seguir el pedido ${pedido.numero_pedido}`}
        className="flex flex-col gap-2 rounded-xl border border-borde bg-fondo p-3 transition-colors hover:border-texto-suave"
      >
        <div className="flex flex-wrap items-start justify-between gap-2">
          <div>
            <p className="font-bold">{pedido.numero_pedido}</p>
            <p className="text-sm text-texto-suave">
              {fecha} · {horaCorta(pedido.fecha_creacion)}
            </p>
          </div>
          <span className={`rounded-full border px-2 py-0.5 text-xs font-medium ${estado.clases}`}>
            {estado.etiqueta}
          </span>
        </div>
        {pedido.resumen.length > 0 && <p className="text-sm">{pedido.resumen.join(', ')}</p>}
        <div className="flex flex-wrap items-center justify-between gap-2 text-sm">
          <span className="font-semibold">{pedido.total ? formatearPrecio(pedido.total) : ''}</span>
          <span aria-hidden="true" className="text-marca-clara">
            {CERRADOS.includes(pedido.estado) ? 'Ver detalle →' : 'Seguir pedido →'}
          </span>
        </div>
      </Link>
    </li>
  )
}

// HU-47 · Orders of the customer, the ones in progress first, each one opens its live tracking
export default function MisPedidos() {
  const [pedidos, setPedidos] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    let vigente = true
    listarMisPedidos()
      .then((datos) => {
        if (vigente) setPedidos(datos)
      })
      .catch((fallo) => {
        if (vigente) setError(interpretarError(fallo).general)
      })
    return () => {
      vigente = false
    }
  }, [])

  const enCurso = pedidos?.filter((pedido) => !CERRADOS.includes(pedido.estado)) ?? []
  const anteriores = pedidos?.filter((pedido) => CERRADOS.includes(pedido.estado)) ?? []

  return (
    <div className="flex flex-col gap-4">
      <header>
        <h1 className="text-2xl font-bold">Mis pedidos</h1>
        <p className="text-texto-suave">Toca un pedido para seguirlo en tiempo real.</p>
      </header>

      {error && <Alerta tipo="error" titulo={error} />}
      {!pedidos && !error && <p className="text-texto-suave">Cargando…</p>}
      {pedidos?.length === 0 && (
        <Alerta tipo="info" titulo="Todavía no tienes pedidos">
          <Link to="/menu" className="text-marca-clara underline underline-offset-4">
            Ir al menú
          </Link>
        </Alerta>
      )}

      {enCurso.length > 0 && (
        <Tarjeta titulo="En curso">
          <ul className="flex flex-col gap-3">
            {enCurso.map((pedido) => (
              <TarjetaPedidoCliente key={pedido.id} pedido={pedido} />
            ))}
          </ul>
        </Tarjeta>
      )}
      {anteriores.length > 0 && (
        <Tarjeta titulo="Anteriores">
          <ul className="flex flex-col gap-3">
            {anteriores.map((pedido) => (
              <TarjetaPedidoCliente key={pedido.id} pedido={pedido} />
            ))}
          </ul>
        </Tarjeta>
      )}
    </div>
  )
}
