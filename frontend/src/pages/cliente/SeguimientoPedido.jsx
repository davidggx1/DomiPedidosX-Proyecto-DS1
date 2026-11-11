import { useCallback, useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { interpretarError } from '../../api/errores.js'
import { cancelarPedido, conectarEstadoPedido, obtenerEstadoPedido } from '../../api/pedidos.js'
import BarraProgresoPedido from '../../components/pedidos/BarraProgresoPedido.jsx'
import Alerta from '../../components/ui/Alerta.jsx'
import Boton from '../../components/ui/Boton.jsx'
import Modal from '../../components/ui/Modal.jsx'
import Tarjeta from '../../components/ui/Tarjeta.jsx'
import { datosEstado } from '../../utils/estadosPedido.js'
import { PASOS_CLIENTE, aplicarEvento, pasosConProgreso, puedeCancelar } from '../../utils/seguimiento.js'

// Reason the backend saves when the customer cancels (backend/pedidos/cancelacion.py)
const MOTIVO_CLIENTE = 'Cancelado por el cliente.'

const VOLVER = (
  <Link to="/mis-pedidos" className="self-start text-marca-clara underline underline-offset-4">
    ← Volver a mis pedidos
  </Link>
)

// HU-47 · The customer follows his order live: every change arrives by WebSocket
// and moves the progress bar without reloading the page.
// HU-25 · While the kitchen has not started it, the customer can cancel it
export default function SeguimientoPedido() {
  const { id } = useParams()
  const [seguimiento, setSeguimiento] = useState(null)
  const [error, setError] = useState(null)
  const [enVivo, setEnVivo] = useState(false)
  const [confirmando, setConfirmando] = useState(false)
  const [cancelando, setCancelando] = useState(false)
  const [errorCancelar, setErrorCancelar] = useState(null)

  const cerrarConfirmacion = useCallback(() => {
    if (!cancelando) setConfirmando(false)
  }, [cancelando])

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

  async function confirmarCancelacion() {
    setCancelando(true)
    setErrorCancelar(null)
    try {
      setSeguimiento(await cancelarPedido(id))
      setConfirmando(false)
    } catch (fallo) {
      setErrorCancelar(fallo.response?.data?.detail ?? interpretarError(fallo).general)
    } finally {
      setCancelando(false)
    }
  }

  const estado = datosEstado(seguimiento.estado)
  const cancelado = seguimiento.estado === 'cancelado'
  const terminado = cancelado || seguimiento.estado === 'entregado'
  const pasoActual = PASOS_CLIENTE.find((paso) => paso.estado === seguimiento.estado)
  const cancelacion = puedeCancelar(seguimiento.estado)
  const motivo = seguimiento.motivo_cancelacion?.trim()

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

      {cancelado && motivo === MOTIVO_CLIENTE ? (
        <Alerta tipo="info" titulo="Cancelaste este pedido">
          <p>Te enviamos la confirmación a tu correo.</p>
          <p className="mt-1 text-sm text-texto-suave">Si ya pagaste, comunícate con la sede para el reembolso.</p>
        </Alerta>
      ) : cancelado ? (
        <Alerta tipo="error" titulo="Tu pedido fue cancelado">
          <p>{motivo ? `Motivo: ${motivo}` : 'La sede canceló el pedido.'}</p>
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

      {!terminado && (
        <div className="flex flex-col items-start gap-2">
          <Boton
            variante="peligro"
            disabled={!cancelacion.puede}
            aria-describedby={cancelacion.motivo ? 'motivo-no-cancelar' : undefined}
            onClick={() => {
              setErrorCancelar(null)
              setConfirmando(true)
            }}
          >
            Cancelar pedido
          </Boton>
          {cancelacion.motivo && (
            <p id="motivo-no-cancelar" className="text-sm text-texto-suave">
              {cancelacion.motivo}
            </p>
          )}
        </div>
      )}

      {confirmando && (
        <Modal
          titulo={`¿Cancelar el pedido ${seguimiento.numero_pedido}?`}
          alCerrar={cerrarConfirmacion}
          acciones={
            <>
              <Boton variante="secundario" disabled={cancelando} onClick={cerrarConfirmacion}>
                No, mantenerlo
              </Boton>
              <Boton variante="peligro" cargando={cancelando} onClick={confirmarCancelacion}>
                Sí, cancelar pedido
              </Boton>
            </>
          }
        >
          {errorCancelar && <Alerta tipo="error" titulo={errorCancelar} className="mb-3" />}
          <p className="text-texto">
            La sede no lo preparará y te enviaremos la confirmación a tu correo. Esta acción no se puede
            deshacer.
          </p>
        </Modal>
      )}
    </div>
  )
}
