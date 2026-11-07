import { useCallback, useEffect, useRef, useState } from 'react'
import api from '../../api/cliente.js'
import Alerta from '../../components/ui/Alerta.jsx'
import Boton from '../../components/ui/Boton.jsx'
import Tarjeta from '../../components/ui/Tarjeta.jsx'

export default function PedidosEntrantes() {
  const [pedidos, setPedidos] = useState([])
  const [cargando, setCargando] = useState(true)
  const [error, setError] = useState(null)
  const [procesando, setProcesando] = useState(false)
  const [estadoConexion, setEstadoConexion] = useState('conectando')

  // Estado para el modal de confirmación de aprobación (HU-28)
  const [pedidoAprobar, setPedidoAprobar] = useState(null)

  const wsRef = useRef(null)

  // Carga inicial HTTP
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
    cargar()
  }, [cargar])

  // WebSocket lifecycle (HU-27)
  useEffect(() => {
    let reconexionTimeout = null

    function conectarWS() {
      const token = localStorage.getItem('access_token') || sessionStorage.getItem('access_token')

      if (!token) {
        setEstadoConexion('desconectado')
        return
      }

      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
      const host = window.location.hostname === 'localhost' ? '127.0.0.1:8000' : window.location.host
      const wsUrl = `${protocol}//${host}/ws/pedidos/entrantes/?token=${token}`

      const socket = new WebSocket(wsUrl)
      wsRef.current = socket

      socket.onopen = () => setEstadoConexion('conectado')

      socket.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data)
          const { tipo, pedido } = data

          if (tipo === 'pedido_nuevo') {
            setPedidos((prev) => {
              if (prev.some((p) => p.id === pedido.id)) return prev
              return [...prev, pedido]
            })
          } else if (tipo === 'pedido_actualizado') {
            setPedidos((prev) => {
              // Si ya no está pendiente de aprobación (recibido o cancelado), se remueve de la lista
              if (pedido.estado !== 'pendiente_aprobacion') {
                return prev.filter((p) => p.id !== pedido.id)
              }
              return prev.map((p) => (p.id === pedido.id ? pedido : p))
            })
          }
        } catch (e) {
          console.error('Error procesando evento WS:', e)
        }
      }

      socket.onerror = () => setEstadoConexion('desconectado')

      socket.onclose = (event) => {
        setEstadoConexion('desconectado')
        if (event.code === 4401) {
          setError('Tu sesión o token ha expirado (4401). Intenta recargar la página.')
          return
        }
        if (event.code === 4403) {
          setError('No tienes permisos o sede asignada para ver pedidos entrantes (4403).')
          return
        }
        reconexionTimeout = window.setTimeout(conectarWS, 5000)
      }
    }

    conectarWS()

    return () => {
      if (reconexionTimeout) window.clearTimeout(reconexionTimeout)
      if (wsRef.current) wsRef.current.close()
    }
  }, [])

  // Confirmar aprobación (HU-28)
  const confirmarAprobacion = async () => {
    if (!pedidoAprobar) return
    setProcesando(true)
    setError(null)

    try {
      // Petición PATCH sin cuerpo según contrato
      await api.patch(`/pedidos/${pedidoAprobar.id}/aprobar/`)

      // Éxito HTTP 200: se remueve de la lista localmente mientras llega el evento WS
      setPedidos((prev) => prev.filter((p) => p.id !== pedidoAprobar.id))
      setPedidoAprobar(null)
    } catch (err) {
      const status = err.response?.status
      const data = err.response?.data

      if (status === 409) {
        // Conflicto: otro operador ya procesó el pedido
        const estadoActual = data?.estado_actual || 'procesado por otro usuario'
        setError(`El pedido #${pedidoAprobar.numero_pedido ?? pedidoAprobar.id} ya fue modificado. Estado actual: ${estadoActual}.`)
        await cargar() // Refrescar lista automáticamente
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
              <p className="text-sm text-texto-suave">Estado: {pedido.estado}</p>
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

              {/* Botón que abre el modal de confirmación */}
              <Boton className="mt-4 w-full" onClick={() => setPedidoAprobar(pedido)}>
                Aprobar pedido
              </Boton>
            </Tarjeta>
          ))}
        </div>
      )}

      {/* Modal de confirmación (HU-28) */}
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