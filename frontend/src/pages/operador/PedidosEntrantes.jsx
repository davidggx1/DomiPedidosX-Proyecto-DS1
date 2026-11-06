import { useCallback, useEffect, useState } from 'react'
import api from '../../api/cliente.js'
import Alerta from '../../components/ui/Alerta.jsx'
import Boton from '../../components/ui/Boton.jsx'
import Tarjeta from '../../components/ui/Tarjeta.jsx'

export default function PedidosEntrantes() {
  const [pedidos, setPedidos] = useState([])
  const [cargando, setCargando] = useState(true)
  const [error, setError] = useState(null)
  const [procesando, setProcesando] = useState(null)

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
    const inicio = window.setTimeout(cargar, 0)
    const intervalo = window.setInterval(cargar, 10000)
    return () => {
      window.clearTimeout(inicio)
      window.clearInterval(intervalo)
    }
  }, [cargar])

  async function aprobar(id) {
    setProcesando(id)
    try {
      await api.post(`/pedidos/${id}/aprobar/`)
      await cargar()
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
        <Boton variante="secundario" onClick={cargar}>Actualizar</Boton>
      </header>
      {error && <Alerta tipo="error" titulo={error} />}
      {cargando ? <p className="text-texto-suave">Cargando pedidos…</p> : pedidos.length === 0 ? (
        <Tarjeta><p className="text-texto-suave">No hay pedidos pendientes.</p></Tarjeta>
      ) : (
        <div className="grid gap-4 md:grid-cols-2">
          {pedidos.map((pedido) => (
            <Tarjeta key={pedido.id} titulo={`Pedido #${pedido.numero_pedido ?? pedido.id}`}>
              <p className="text-sm text-texto-suave">Estado: {pedido.estado}</p>
              {pedido.descripcion && <p className="mt-2">{pedido.descripcion}</p>}
              <Boton className="mt-4" onClick={() => aprobar(pedido.id)} cargando={procesando === pedido.id}>
                Aprobar pedido
              </Boton>
            </Tarjeta>
          ))}
        </div>
      )}
    </div>
  )
}
