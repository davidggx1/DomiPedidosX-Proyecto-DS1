import { useCallback, useEffect, useState } from 'react'
import {
  cambiarEstadoPedido,
  crearUrlWebSocketCocina,
  obtenerComandaCocina,
  obtenerTableroCocina,
} from '../../api/pedidos.js'
import { useAuth } from '../../auth/useAuth.js'

const COLUMNAS = [
  { estado: 'recibido', titulo: 'Recibido', descripcion: 'Pedidos aprobados que esperan preparación', color: 'border-sky-500' },
  { estado: 'en_preparacion', titulo: 'En preparación', descripcion: 'Pedidos que está preparando cocina', color: 'border-amber-500' },
  { estado: 'listo_despacho', titulo: 'Listo para despacho', descripcion: 'Pedidos terminados y pendientes de recogida', color: 'border-exito' },
]

const ETIQUETAS_ESTADO = {
  en_preparacion: 'Iniciar preparación',
  listo_despacho: 'Marcar como listo',
  cancelado: 'Cancelar pedido',
}

function mensajeError(error) {
  const datos = error.response?.data
  if (typeof datos?.detail === 'string') return datos.detail
  if (typeof datos?.motivo === 'string') return datos.motivo
  if (typeof datos === 'string') return datos
  return 'No fue posible completar la operación. Comprueba tu conexión e inténtalo de nuevo.'
}

function TarjetaPedido({ pedido, alCambiarEstado, alVerComanda, ocupado }) {
  return (
    <article className="rounded-xl border border-borde bg-superficie p-4 shadow-sm">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-xs font-semibold uppercase tracking-wide text-texto-suave">Pedido</p>
          <h3 className="text-xl font-bold">#{pedido.numero_pedido}</h3>
        </div>
        {pedido.tiene_cambios && (
          <span className="rounded-full bg-aviso/15 px-2 py-1 text-xs font-semibold text-aviso">Personalizado</span>
        )}
      </div>

      <ul className="mt-3 space-y-1 text-sm text-texto">
        {pedido.resumen?.map((linea, indice) => <li key={`${pedido.id}-${indice}`}>{linea}</li>)}
      </ul>

      {(pedido.tiene_notas || pedido.tiene_cambios) && (
        <p className="mt-3 rounded-lg border border-aviso/40 bg-aviso/10 px-3 py-2 text-xs text-aviso">
          Revisa las notas y personalizaciones antes de preparar.
        </p>
      )}

      <div className="mt-4 flex flex-wrap gap-2">
        <button
          type="button"
          onClick={() => alVerComanda(pedido.id)}
          className="min-h-10 rounded-lg border border-borde px-3 text-sm font-medium hover:bg-superficie-alta"
        >
          Ver comanda
        </button>
        {pedido.siguientes_estados?.map((estado) => (
          <button
            key={estado}
            type="button"
            disabled={ocupado}
            onClick={() => alCambiarEstado(pedido, estado)}
            className={`min-h-10 rounded-lg px-3 text-sm font-semibold text-white transition-colors disabled:cursor-wait disabled:opacity-50 ${
              estado === 'cancelado' ? 'bg-neutral-700 hover:bg-neutral-600' : 'bg-marca hover:bg-marca-oscura'
            }`}
          >
            {ocupado ? 'Guardando…' : ETIQUETAS_ESTADO[estado] ?? estado}
          </button>
        ))}
      </div>
    </article>
  )
}

function ModalComanda({ comanda, alCerrar }) {
  if (!comanda) return null

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 p-4" role="presentation" onMouseDown={(evento) => {
      if (evento.target === evento.currentTarget) alCerrar()
    }}>
      <section
        role="dialog"
        aria-modal="true"
        aria-labelledby="titulo-comanda"
        className="max-h-[90vh] w-full max-w-2xl overflow-y-auto rounded-2xl border border-borde bg-superficie p-5 shadow-2xl"
      >
        <div className="flex items-start justify-between gap-4">
          <div>
            <p className="text-sm text-texto-suave">Comanda de cocina</p>
            <h2 id="titulo-comanda" className="text-2xl font-bold">Pedido #{comanda.numero_pedido}</h2>
            <p className="mt-1 text-sm text-texto-suave">Estado: {comanda.estado_nombre}</p>
          </div>
          <button type="button" onClick={alCerrar} className="min-h-10 rounded-lg border border-borde px-3 text-sm hover:bg-superficie-alta">Cerrar</button>
        </div>

        {comanda.notas && (
          <div className="mt-5 rounded-lg border border-aviso/50 bg-aviso/10 p-3">
            <h3 className="font-semibold text-aviso">Notas del pedido</h3>
            <p className="mt-1 text-sm">{comanda.notas}</p>
          </div>
        )}

        <div className="mt-5 space-y-3">
          {comanda.lineas?.map((linea) => (
            <article key={linea.id} className="rounded-xl border border-borde p-4">
              <div className="flex flex-wrap items-baseline justify-between gap-2">
                <h3 className="font-semibold">{linea.cantidad} × {linea.nombre}{linea.tamano ? ` (${linea.tamano})` : ''}</h3>
              </div>
              {linea.adiciones?.length > 0 && <p className="mt-2 text-sm text-exito">Adiciones: {linea.adiciones.map((item) => `${item.cantidad} × ${item.nombre}`).join(', ')}</p>}
              {linea.sin?.length > 0 && <p className="mt-2 text-sm font-semibold text-error">Sin: {linea.sin.join(', ')}</p>}
              {linea.observaciones && <p className="mt-2 text-sm text-texto-suave">Indicaciones: {linea.observaciones}</p>}
            </article>
          ))}
        </div>
        <button type="button" onClick={alCerrar} className="mt-5 min-h-11 w-full rounded-lg bg-marca px-4 font-semibold text-white hover:bg-marca-oscura">Listo</button>
      </section>
    </div>
  )
}

export default function TableroCocina() {
  const { token } = useAuth()
  const [tablero, setTablero] = useState({ recibido: [], en_preparacion: [], listo_despacho: [] })
  const [cargando, setCargando] = useState(true)
  const [error, setError] = useState('')
  const [conexion, setConexion] = useState(token ? 'conectando' : 'sin sesión')
  const [pedidoOcupado, setPedidoOcupado] = useState(null)
  const [comanda, setComanda] = useState(null)
  const [cargandoComanda, setCargandoComanda] = useState(false)

  const cargarTablero = useCallback(async (silencioso = false) => {
    if (!silencioso) setCargando(true)
    try {
      const datos = await obtenerTableroCocina()
      setTablero({
        recibido: datos.recibido ?? [],
        en_preparacion: datos.en_preparacion ?? [],
        listo_despacho: datos.listo_despacho ?? [],
      })
      setError('')
    } catch (solicitudError) {
      setError(mensajeError(solicitudError))
    } finally {
      setCargando(false)
    }
  }, [])

  useEffect(() => {
    cargarTablero()
  }, [cargarTablero])

  useEffect(() => {
    if (!token) return undefined

    let socket
    let temporizador
    let cancelado = false

    const conectar = () => {
      if (cancelado) return
      socket = new WebSocket(crearUrlWebSocketCocina(token))

      socket.onopen = () => {
        setConexion('conectado')
        cargarTablero(true)
      }
      socket.onmessage = (evento) => {
        try {
          const mensaje = JSON.parse(evento.data)
          if (mensaje.tipo === 'pedido.actualizado') cargarTablero(true)
        } catch {
          // Ignora mensajes que no sean JSON válido; no interrumpe el tablero.
        }
      }
      socket.onerror = () => setConexion('error')
      socket.onclose = (evento) => {
        setConexion(evento.code === 4401 || evento.code === 4403 ? 'sin autorización' : 'desconectado')
        if (!cancelado && evento.code !== 4401 && evento.code !== 4403) {
          temporizador = window.setTimeout(conectar, 3000)
        }
      }
    }

    conectar()
    return () => {
      cancelado = true
      window.clearTimeout(temporizador)
      socket?.close()
    }
  }, [token, cargarTablero])

  async function manejarCambioEstado(pedido, nuevoEstado) {
    let motivo = ''
    if (nuevoEstado === 'cancelado') {
      motivo = window.prompt('Indica el motivo de cancelación del pedido:') ?? ''
      if (!motivo.trim()) return
    }

    setPedidoOcupado(pedido.id)
    setError('')
    try {
      await cambiarEstadoPedido(pedido.id, nuevoEstado, motivo)
      await cargarTablero(true)
    } catch (solicitudError) {
      setError(mensajeError(solicitudError))
    } finally {
      setPedidoOcupado(null)
    }
  }

  async function manejarVerComanda(pedidoId) {
    setCargandoComanda(true)
    setComanda(null)
    try {
      const datos = await obtenerComandaCocina(pedidoId)
      setComanda(datos)
    } catch (solicitudError) {
      setError(mensajeError(solicitudError))
    } finally {
      setCargandoComanda(false)
    }
  }

  const totalPedidos = COLUMNAS.reduce((total, columna) => total + tablero[columna.estado].length, 0)

  return (
    <section className="space-y-6">
      <header className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="text-sm font-semibold uppercase tracking-wider text-marca-clara">Operación de sede</p>
          <h1 className="mt-1 text-3xl font-bold">Tablero de cocina</h1>
          <p className="mt-2 text-sm text-texto-suave">Pedidos aprobados, organizados por su estado de preparación.</p>
        </div>
        <div className="flex flex-wrap items-center gap-3">
          <span className="rounded-full border border-borde bg-superficie px-3 py-2 text-sm">{totalPedidos} pedidos activos</span>
          <span className={`rounded-full px-3 py-2 text-xs font-semibold ${conexion === 'conectado' ? 'bg-exito/15 text-exito' : 'bg-aviso/15 text-aviso'}`}>
            {conexion === 'conectado' ? '● Tiempo real conectado' : `● Tiempo real: ${conexion}`}
          </span>
          <button type="button" onClick={() => cargarTablero()} className="min-h-10 rounded-lg border border-borde px-3 text-sm font-semibold hover:bg-superficie-alta">
            Actualizar
          </button>
        </div>
      </header>

      {error && (
        <div role="alert" className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-error/50 bg-error/10 p-4 text-sm text-error">
          <p>{error}</p>
          <button type="button" onClick={() => cargarTablero()} className="font-semibold underline">Reintentar</button>
        </div>
      )}

      {cargando ? (
        <p className="rounded-xl border border-borde bg-superficie p-6 text-center text-texto-suave">Cargando pedidos de la sede…</p>
      ) : (
        <div className="grid grid-cols-1 items-start gap-4 lg:grid-cols-3">
          {COLUMNAS.map((columna) => (
            <section key={columna.estado} aria-labelledby={`columna-${columna.estado}`} className={`min-w-0 rounded-xl border-t-4 ${columna.color} bg-superficie-alta/50 p-3`}>
              <header className="mb-3 flex items-start justify-between gap-2 px-1">
                <div>
                  <h2 id={`columna-${columna.estado}`} className="font-bold">{columna.titulo}</h2>
                  <p className="mt-1 text-xs text-texto-suave">{columna.descripcion}</p>
                </div>
                <span className="rounded-full bg-superficie px-2.5 py-1 text-sm font-bold">{tablero[columna.estado].length}</span>
              </header>
              <div className="space-y-3">
                {tablero[columna.estado].map((pedido) => (
                  <TarjetaPedido
                    key={pedido.id}
                    pedido={pedido}
                    ocupado={pedidoOcupado === pedido.id}
                    alCambiarEstado={manejarCambioEstado}
                    alVerComanda={manejarVerComanda}
                  />
                ))}
                {tablero[columna.estado].length === 0 && (
                  <p className="rounded-lg border border-dashed border-borde px-3 py-8 text-center text-sm text-texto-suave">No hay pedidos en esta columna.</p>
                )}
              </div>
            </section>
          ))}
        </div>
      )}

      {cargandoComanda && <p role="status" className="text-center text-sm text-texto-suave">Cargando comanda…</p>}
      <ModalComanda comanda={comanda} alCerrar={() => setComanda(null)} />
    </section>
  )
}
