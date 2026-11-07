import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { interpretarError } from '../../api/errores.js'
import { conectarEstadoPedido, obtenerEstadoPedido } from '../../api/pedidos.js'
import BarraProgresoPedido from '../../components/pedidos/BarraProgresoPedido.jsx'
import Alerta from '../../components/ui/Alerta.jsx'
import Tarjeta from '../../components/ui/Tarjeta.jsx'
import { datosEstado } from '../../utils/estadosPedido.js'
import { PASOS_CLIENTE, aplicarEvento, pasosConProgreso } from '../../utils/seguimiento.js'

const VOLVER = (
  <Link to="/mis-pedidos" className="self-start text-marca-clara underline underline-offset-4">
    ← Volver a mis pedidos
  </Link>
)

// HU-47 · The customer follows his order live: every change arrives by WebSocket
// and moves the progress bar without reloading the page
export default function SeguimientoPedido() {
  const { id } = useParams()
  const [seguimiento, setSeguimiento] = useState(null)
  const [error, setError] = useState(null)
  const [enVivo, setEnVivo] = useState(false)

  useEffect(() => {
    let vigente = true

    function cargar() {
      obtenerEstadoPedido(id)
        .then((datos) => {
          if (!vigente) return
          setSeguimiento(datos)
          setError(null)
        })
        .catch((fallo) => {
          if (!vigente) return
          setError(
            fallo.response?.status === 404
              ? 'No encontramos este pedido en tu cuenta.'
              : interpretarError(fallo).general,
          )
        })
    }

    cargar()
    const cerrar = conectarEstadoPedido(id, {
      alMensaje: (evento) => {
        if (vigente) setSeguimiento((actual) => (actual ? aplicarEvento(actual, evento) : actual))
      },
      // after a cut, ask again so no change is lost
      alReconectar: cargar,
      alCambiarConexion: (conectado) => {
        if (vigente) setEnVivo(conectado)
      },
    })
    return () => {
      vigente = false
      cerrar()
    }
  }, [id])

  if (!seguimiento) {
    return (
      <div className="flex flex-col gap-4">
        {VOLVER}
        {error ? <Alerta tipo="error" titulo={error} /> : <p className="text-texto-suave">Cargando…</p>}
      </div>
    )
  }

  const estado = datosEstado(seguimiento.estado)
  const cancelado = seguimiento.estado === 'cancelado'
  const terminado = cancelado || seguimiento.estado === 'entregado'
  const pasoActual = PASOS_CLIENTE.find((paso) => paso.estado === seguimiento.estado)

  return (
    <div className="flex flex-col gap-4">
      {VOLVER}

      <header className="flex flex-wrap items-center justify-between gap-2">
        <h1 className="text-2xl font-bold">Pedido {seguimiento.numero_pedido}</h1>
        <div className="flex flex-wrap gap-2">
          <span className={`rounded-full border px-3 py-1 text-sm font-medium ${estado.clases}`}>
            {estado.etiqueta}
          </span>
          {!terminado && (
            <span
              className={`rounded-full border px-3 py-1 text-sm font-medium ${
                enVivo ? 'border-exito text-exito' : 'border-borde text-texto-suave'
              }`}
            >
              {enVivo ? 'En vivo' : 'Reconectando…'}
            </span>
          )}
        </div>
      </header>

      {error && <Alerta tipo="error" titulo={error} />}

      {cancelado ? (
        <Alerta tipo="error" titulo="Tu pedido fue cancelado">
          <p>
            {seguimiento.motivo_cancelacion?.trim()
              ? `Motivo: ${seguimiento.motivo_cancelacion.trim()}`
              : 'La sede canceló el pedido.'}
          </p>
          <p className="mt-1 text-sm text-texto-suave">Si ya pagaste, comunícate con la sede para el reembolso.</p>
        </Alerta>
      ) : (
        <Tarjeta>
          <div aria-live="polite" className="mb-4">
            <p className="text-lg font-semibold">{pasoActual?.titulo}</p>
            <p className="text-texto-suave">{pasoActual?.texto}</p>
          </div>
          <BarraProgresoPedido pasos={pasosConProgreso(seguimiento.estado, seguimiento.historial)} />
        </Tarjeta>
      )}
    </div>
  )
}
