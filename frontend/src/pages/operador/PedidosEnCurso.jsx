import { useCallback, useEffect, useState } from 'react'
import { interpretarError } from '../../api/errores.js'
import { obtenerPedidosEnCurso } from '../../api/pedidos.js'
import ModalCancelarPedido from '../../components/operador/ModalCancelarPedido.jsx'
import Alerta from '../../components/ui/Alerta.jsx'
import Boton from '../../components/ui/Boton.jsx'
import Tarjeta from '../../components/ui/Tarjeta.jsx'
import { datosEstado } from '../../utils/estadosPedido.js'

const INTERVALO_MS = 15000

const ORIGEN = { web: 'Web', telefonico: 'Teléfono', mostrador: 'Mostrador' }

function hora(fecha) {
  return new Date(fecha).toLocaleTimeString('es-CO', { hour: '2-digit', minute: '2-digit' })
}

// HU-34 · Orders of the sede that are not delivered or cancelled, each one can be cancelled
export default function PedidosEnCurso() {
  const [pedidos, setPedidos] = useState([])
  const [cargando, setCargando] = useState(true)
  const [errorCarga, setErrorCarga] = useState(null)
  const [recarga, setRecarga] = useState(0)
  const [cancelando, setCancelando] = useState(null) // order shown in the modal
  const [mensaje, setMensaje] = useState(null)

  useEffect(() => {
    let vigente = true
    function cargar() {
      obtenerPedidosEnCurso()
        .then((lista) => {
          if (!vigente) return
          setPedidos(lista)
          setErrorCarga(null)
        })
        .catch((error) => {
          if (vigente) setErrorCarga(interpretarError(error).general)
        })
        .finally(() => {
          if (vigente) setCargando(false)
        })
    }
    cargar()
    const temporizador = setInterval(cargar, INTERVALO_MS)
    return () => {
      vigente = false
      clearInterval(temporizador)
    }
  }, [recarga])

  const cerrarModal = useCallback(() => setCancelando(null), [])

  const alCancelar = useCallback((pedido) => {
    setCancelando(null)
    setMensaje({ tipo: 'exito', texto: `El pedido ${pedido.numero_pedido} quedó cancelado.` })
    setRecarga((n) => n + 1)
  }, [])

  return (
    <div className="flex flex-col gap-4">
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold">Pedidos en curso</h1>
          <p className="text-texto-suave">
            Pedidos de la sede que todavía no se entregan. Desde aquí puedes cancelarlos indicando el motivo.
          </p>
        </div>
        <Boton variante="secundario" onClick={() => setRecarga((n) => n + 1)}>
          Actualizar ahora
        </Boton>
      </header>

      {mensaje && <Alerta tipo={mensaje.tipo} titulo={mensaje.texto} />}
      {errorCarga && <Alerta tipo="error" titulo={errorCarga} />}
      {cargando && <p className="text-texto-suave">Cargando…</p>}

      {!cargando && (
        <Tarjeta titulo={`Pedidos activos (${pedidos.length})`}>
          {pedidos.length === 0 ? (
            <p className="text-texto-suave">No hay pedidos en curso.</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead className="text-texto-suave">
                  <tr className="border-b border-borde">
                    <th className="py-2 pr-3 font-medium">Pedido</th>
                    <th className="py-2 pr-3 font-medium">Estado</th>
                    <th className="py-2 pr-3 font-medium">Cliente</th>
                    <th className="py-2 pr-3 font-medium">Productos</th>
                    <th className="py-2 pr-3 font-medium">Domiciliario</th>
                    <th className="py-2 font-medium">
                      <span className="sr-only">Acciones</span>
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {pedidos.map((pedido) => {
                    const estado = datosEstado(pedido.estado)
                    return (
                      <tr key={pedido.id} className="border-b border-borde align-top last:border-0">
                        <td className="py-2 pr-3">
                          <p className="font-semibold">{pedido.numero_pedido}</p>
                          <p className="text-texto-suave">
                            {ORIGEN[pedido.origen] ?? pedido.origen} · {hora(pedido.fecha_creacion)}
                          </p>
                        </td>
                        <td className="py-2 pr-3">
                          <span className={`rounded-full border px-2 py-0.5 text-xs ${estado.clases}`}>
                            {estado.etiqueta}
                          </span>
                        </td>
                        <td className="py-2 pr-3">{pedido.cliente ?? 'Sin cliente'}</td>
                        <td className="py-2 pr-3">{pedido.resumen.join(', ')}</td>
                        <td className="py-2 pr-3">{pedido.repartidor?.nombre ?? '—'}</td>
                        <td className="py-2 text-right">
                          <Boton variante="peligro" onClick={() => setCancelando(pedido)}>
                            Cancelar
                          </Boton>
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          )}
        </Tarjeta>
      )}

      {cancelando && (
        <ModalCancelarPedido pedido={cancelando} alCerrar={cerrarModal} alCancelar={alCancelar} />
      )}
    </div>
  )
}
