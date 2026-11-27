import { useCallback, useEffect, useState } from 'react'
import api from '../../api/cliente.js'
import { conectarSocket } from '../../api/tiempoReal.js'
import Alerta from '../../components/ui/Alerta.jsx'
import Boton from '../../components/ui/Boton.jsx'
import Tarjeta from '../../components/ui/Tarjeta.jsx'
import EstadoCapacidadSede from '../../components/pedidos/EstadoCapacidadSede.jsx'
import { useEstadoCapacidad } from '../../capacidad/useEstadoCapacidad.js'
import { capacidadDeEvento } from '../../utils/capacidad.js'
import { datosEstado } from '../../utils/estadosPedido.js'

export default function PedidosEntrantes() {
  const [pedidos, setPedidos] = useState([])
  const [cargando, setCargando] = useState(true)
  const [error, setError] = useState(null)
  const [procesando, setProcesando] = useState(false)
  const [estadoConexion, setEstadoConexion] = useState('conectando')

  const [pedidoAprobar, setPedidoAprobar] = useState(null)

  // HU-60: capacity of the sede. The WebSocket updates it live, the request
  // every minute covers what no order event shows (a change of slot by the clock)
  const {
    estado: capacidadSede,
    refrescar: refrescarCapacidad,
    actualizar: actualizarCapacidad,
  } = useEstadoCapacidad({ cadaMs: 60000 })

  const cargar = useCallback(async () => {
    try {
      setError(null)
      const { data } = await api.get('/pedidos/entrantes/')
      setPedidos(Array.isArray(data) ? data : data.results ?? [])
    } catch {
      setError('No fue posible cargar los pedidos entrantes.')
    } finally {
      setCargando(false)
    }
  }, [])

  useEffect(() => {
    let activo = true
    api.get('/pedidos/entrantes/')
      .then(({ data }) => {
        if (activo) {
          setPedidos(Array.isArray(data) ? data : data.results ?? [])
          setCargando(false)
        }
      })
      .catch(() => {
        if (activo) {
          setError('No fue posible cargar los pedidos entrantes.')
          setCargando(false)
        }
      })
    return () => { activo = false }
  }, [])

  // Live orders of the sede. Same socket helper as the rest of the app: it reads
  // the saved session and reconnects by itself
  useEffect(() => {
    return conectarSocket('/ws/pedidos/entrantes/', {
      alCambiarConexion: (conectado) => {
        setEstadoConexion(conectado ? 'conectado' : 'desconectado')
        // events sent while the socket was down were lost
        if (conectado) refrescarCapacidad()
      },
      alReconectar: cargar,
      alRechazar: (codigo) => {
        setError(
          codigo === 4401
            ? 'Tu sesión expiró. Inicia sesión de nuevo para recibir pedidos en vivo.'
            : 'No tienes permisos o sede asignada para ver pedidos entrantes.',
        )
      },
      alMensaje: (data) => {
        const capacidadNueva = capacidadDeEvento(data)
        if (capacidadNueva) {
          actualizarCapacidad(capacidadNueva)
          return
        }

        const { tipo, pedido } = data

        if (tipo === 'pedido_nuevo') {
          setPedidos((prev) => {
            if (prev.some((p) => p.id === pedido.id)) return prev
            return [...prev, pedido]
          })
        } else if (tipo === 'pedido_actualizado') {
          setPedidos((prev) => {
            if (pedido.estado !== 'pendiente_aprobacion') {
              return prev.filter((p) => p.id !== pedido.id)
            }
            return prev.map((p) => (p.id === pedido.id ? pedido : p))
          })
        }
      },
    })
  }, [actualizarCapacidad, refrescarCapacidad, cargar])

  const confirmarAprobacion = async () => {
    if (!pedidoAprobar) return
    setProcesando(true)
    setError(null)

    try {
      await api.patch(`/pedidos/${pedidoAprobar.id}/aprobar/`)
      setPedidos((prev) => prev.filter((p) => p.id !== pedidoAprobar.id))
      setPedidoAprobar(null)
    } catch (err) {
      const status = err.response?.status
      const data = err.response?.data

      if (status === 409) {
        const estadoActual = data?.estado_actual || 'procesado por otro usuario'
        setError(`El pedido #${pedidoAprobar.numero_pedido ?? pedidoAprobar.id} ya fue modificado. Estado actual: ${estadoActual}.`)
        await cargar()
      } else if (status === 404) {
        setError('El pedido ya no existe o pertenece a otra sede.')
        await cargar()
      } else if (status === 403) {
        setError('No tienes permisos suficientes para aprobar pedidos.')
      } else {
        setError('No fue posible aprobar el pedido. Inténtalo de nuevo.')
      }
      setPedidoAprobar(null)
    } finally {
      setProcesando(false)
    }
  }

  return (
    <div className="flex flex-col gap-4">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold">Pedidos entrantes</h1>
          <p className="text-texto-suave">Revisa y aprueba los pedidos antes de enviarlos a cocina.</p>
        </div>
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-1.5 text-sm text-texto-suave">
            <span
              className={`h-2.5 w-2.5 rounded-full ${
                estadoConexion === 'conectado'
                  ? 'bg-verde'
                  : estadoConexion === 'conectando'
                  ? 'bg-amarillo animate-pulse'
                  : 'bg-rojo'
              }`}
            />
            <span className="capitalize">{estadoConexion}</span>
          </div>
          <Boton variante="secundario" onClick={cargar}>
            Actualizar
          </Boton>
        </div>
      </header>

      <EstadoCapacidadSede capacidad={capacidadSede} />

      {error && <Alerta tipo="error" titulo={error} />}

      {cargando ? (
        <p className="text-texto-suave">Cargando pedidos…</p>
      ) : pedidos.length === 0 ? (
        <Tarjeta>
          <p className="text-texto-suave">No hay pedidos pendientes.</p>
        </Tarjeta>
      ) : (
        <div className="grid gap-4 md:grid-cols-2">
          {pedidos.map((pedido) => (
            <Tarjeta key={pedido.id} titulo={`Pedido #${pedido.numero_pedido ?? pedido.id}`}>
              <p className="text-sm text-texto-suave">Estado: {datosEstado(pedido.estado).etiqueta}</p>
              {pedido.cliente && (
                <p className="text-sm mt-1">
                  <strong>Cliente:</strong> {pedido.cliente}
                </p>
              )}
              {pedido.entrega_direccion && (
                <p className="text-sm mt-1">
                  <strong>Dirección:</strong> {pedido.entrega_direccion}{' '}
                  {pedido.entrega_barrio ? `(${pedido.entrega_barrio})` : ''}
                </p>
              )}
              {pedido.descripcion && <p className="mt-2 text-sm">{pedido.descripcion}</p>}

              {Array.isArray(pedido.detalles) && pedido.detalles.length > 0 && (
                <div className="mt-3 rounded-lg border border-borde bg-fondo p-3 text-xs space-y-1">
                  <p className="font-semibold">Detalle:</p>
                  {pedido.detalles.map((det, idx) => (
                    <p key={idx}>
                      {det.cantidad}x {det.nombre} {det.tamano ? `(${det.tamano})` : ''}
                    </p>
                  ))}
                </div>
              )}

              <Boton className="mt-4 w-full" onClick={() => setPedidoAprobar(pedido)}>
                Aprobar pedido
              </Boton>
            </Tarjeta>
          ))}
        </div>
      )}

      {pedidoAprobar && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-negro/50 p-4">
          <div className="w-full max-w-md rounded-xl border border-borde bg-superficie p-6 shadow-lg">
            <h3 className="text-lg font-bold">Aprobar Pedido</h3>
            <p className="mt-2 text-sm text-texto-suave">
              ¿Estás seguro de que deseas aprobar el pedido{' '}
              <strong>#{pedidoAprobar.numero_pedido ?? pedidoAprobar.id}</strong>? El pedido pasará a cocina para su preparación.
            </p>

            <div className="mt-6 flex justify-end gap-3">
              <Boton
                variante="secundario"
                onClick={() => setPedidoAprobar(null)}
                disabled={procesando}
              >
                Cancelar
              </Boton>
              <Boton
                onClick={confirmarAprobacion}
                cargando={procesando}
              >
                Sí, aprobar
              </Boton>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}