import { useCallback, useEffect, useRef, useState } from 'react'
import api from '../../api/cliente.js'
import Alerta from '../../components/ui/Alerta.jsx'
import Boton from '../../components/ui/Boton.jsx'
import Tarjeta from '../../components/ui/Tarjeta.jsx'

export default function PedidosEntrantes() {
  const [pedidos, setPedidos] = useState([])
  const [cargando, setCargando] = useState(true)
  const [error, setError] = useState(null)
  const [procesando, setProcesando] = useState(null)
  const [estadoConexion, setEstadoConexion] = useState('conectando')
  const wsRef = useRef(null)

  // Carga inicial HTTP: GET /api/pedidos/entrantes/
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

  // Carga inicial al montar el componente
  useEffect(() => {
    cargar()
  }, [cargar])

  // Conexión en tiempo real con WebSocket
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

      socket.onopen = () => {
        setEstadoConexion('conectado')
      }

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
              // Si ya no está en pendiente_aprobacion (aprobado o cancelado), se elimina
              if (pedido.estado !== 'pendiente_aprobacion') {
                return prev.filter((p) => p.id !== pedido.id)
              }
              // Si sigue pendiente_aprobacion, se actualiza en la lista
              return prev.map((p) => (p.id === pedido.id ? pedido : p))
            })
          }
        } catch (e) {
          console.error('Error al procesar evento WS:', e)
        }
      }

      socket.onerror = () => {
        setEstadoConexion('desconectado')
      }

      socket.onclose = (event) => {
        setEstadoConexion('desconectado')

        if (event.code === 4401) {
          setError('Tu sesión o token ha expirado (4401). Intenta recargar o iniciar sesión.')
          return
        }
        if (event.code === 4403) {
          setError('No tienes permisos o sede asignada para ver pedidos entrantes (4403).')
          return
        }

        // Reconexión automática
        reconexionTimeout = window.setTimeout(conectarWS, 5000)
      }
    }

    conectarWS()

    return () => {
      if (reconexionTimeout) window.clearTimeout(reconexionTimeout)
      if (wsRef.current) wsRef.current.close()
    }
  }, [])

  async function aprobar(id) {
    setProcesando(id)
    try {
      // Usar PATCH en lugar de POST (HU-28)
      await api.patch(`/pedidos/${id}/aprobar/`)
    } catch {
      setError('No fue posible aprobar el pedido. Actualiza e inténtalo de nuevo.')
    } finally {
      setProcesando(null)
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

              {/* Lista de detalles si la API los retorna */}
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

              <Boton className="mt-4 w-full" onClick={() => aprobar(pedido.id)} cargando={procesando === pedido.id}>
                Aprobar pedido
              </Boton>
            </Tarjeta>
          ))}
        </div>
      )}
    </div>
  )
}