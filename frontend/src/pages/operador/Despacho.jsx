import { useEffect, useState } from 'react'
import {
  asignarRepartidor,
  listarPedidosDespacho,
  listarRepartidores,
  retirarRepartidor,
} from '../../api/despacho.js'
import { interpretarError } from '../../api/errores.js'
import TarjetaDespacho from '../../components/despacho/TarjetaDespacho.jsx'
import Alerta from '../../components/ui/Alerta.jsx'
import Boton from '../../components/ui/Boton.jsx'
import Tarjeta from '../../components/ui/Tarjeta.jsx'

// how often the lists ask the server for changes
const INTERVALO_MS = 10000

// The backend answers errors as { detail } or { repartidor: "..." }
function mensajeDeError(error) {
  const { general, campos } = interpretarError(error)
  return campos.repartidor ?? general
}

function textoEstado(repartidor) {
  if (repartidor.pedidos_activos === 0) return 'Libre'
  return repartidor.pedidos_activos === 1 ? 'Ocupado: 1 entrega' : `Ocupado: ${repartidor.pedidos_activos} entregas`
}

// HU-35 · Ready orders on one side, available repartidores on the other
export default function Despacho() {
  const [pedidos, setPedidos] = useState([])
  const [repartidores, setRepartidores] = useState([])
  const [cargando, setCargando] = useState(true)
  const [errorCarga, setErrorCarga] = useState(null)
  const [recarga, setRecarga] = useState(0) // bump it to load the lists again
  const [ahora, setAhora] = useState(() => Date.now())
  const [moviendo, setMoviendo] = useState(null) // id of the order being changed
  const [mensaje, setMensaje] = useState(null)

  useEffect(() => {
    let vigente = true

    function cargar() {
      Promise.all([listarPedidosDespacho(), listarRepartidores({ disponible: true })])
        .then(([listaPedidos, listaRepartidores]) => {
          if (!vigente) return
          setPedidos(listaPedidos)
          setRepartidores(listaRepartidores)
          setErrorCarga(null)
          setAhora(Date.now())
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

  // an assigned repartidor already counts as busy, so only free ones can take a new order
  const libres = repartidores.filter((repartidor) => repartidor.pedidos_activos === 0)
  // HU-36: orders the system could not assign because nobody was free
  const sinAsignar = pedidos.filter((pedido) => !pedido.repartidor).length

  async function ejecutar(pedido, accion, textoExito) {
    setMoviendo(pedido.id)
    setMensaje(null)
    try {
      await accion()
      setMensaje({ tipo: 'exito', texto: textoExito })
    } catch (error) {
      setMensaje({ tipo: 'error', texto: mensajeDeError(error) })
    } finally {
      setMoviendo(null)
      setRecarga((numero) => numero + 1)
    }
  }

  function asignar(pedido, repartidorId) {
    const repartidor = repartidores.find((candidato) => candidato.id === repartidorId)
    const nombre = repartidor ? `${repartidor.nombres} ${repartidor.apellidos}` : 'el repartidor'
    return ejecutar(
      pedido,
      () => asignarRepartidor(pedido.id, repartidorId),
      `El pedido ${pedido.numero_pedido} se asignó a ${nombre}.`,
    )
  }

  function retirar(pedido) {
    if (!window.confirm(`¿Quitar la asignación del pedido ${pedido.numero_pedido}?`)) return
    return ejecutar(
      pedido,
      () => retirarRepartidor(pedido.id),
      `Se quitó la asignación del pedido ${pedido.numero_pedido}.`,
    )
  }

  return (
    <div className="flex flex-col gap-4">
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold">Repartidores</h1>
          <p className="text-texto-suave">
            Los pedidos listos se asignan solos al repartidor libre que lleva más tiempo esperando. Si no
            hay ninguno libre, asígnalo tú. Se actualiza solo cada {INTERVALO_MS / 1000} segundos.
          </p>
        </div>
        <Boton variante="secundario" onClick={() => setRecarga((numero) => numero + 1)}>
          Actualizar ahora
        </Boton>
      </header>

      {mensaje && <Alerta tipo={mensaje.tipo} titulo={mensaje.texto} />}
      {errorCarga && <Alerta tipo="error" titulo={errorCarga} />}
      {!cargando && sinAsignar > 0 && (
        <Alerta
          tipo="aviso"
          titulo={
            sinAsignar === 1 ? 'Hay 1 pedido sin repartidor' : `Hay ${sinAsignar} pedidos sin repartidor`
          }
        >
          {libres.length === 0
            ? 'No hay repartidores libres en este momento. Asígnalos cuando alguno se libere.'
            : 'Ya hay repartidores libres: asígnalos desde la tarjeta del pedido.'}
        </Alerta>
      )}
      {cargando && <p className="text-texto-suave">Cargando…</p>}

      {!cargando && (
        <div className="grid gap-6 lg:grid-cols-[minmax(0,3fr)_minmax(0,2fr)]">
          <Tarjeta titulo={`Pedidos listos para despacho (${pedidos.length})`}>
            {pedidos.length === 0 ? (
              <p className="text-texto-suave">No hay pedidos listos para despachar.</p>
            ) : (
              <ul className="flex flex-col gap-3">
                {pedidos.map((pedido) => (
                  <TarjetaDespacho
                    key={pedido.id}
                    pedido={pedido}
                    libres={libres}
                    ahora={ahora}
                    ocupado={moviendo === pedido.id}
                    alAsignar={asignar}
                    alRetirar={retirar}
                  />
                ))}
              </ul>
            )}
          </Tarjeta>

          <Tarjeta titulo={`Repartidores disponibles (${repartidores.length})`}>
            {repartidores.length === 0 ? (
              <p className="text-texto-suave">Ningún repartidor está disponible ahora.</p>
            ) : (
              <ul className="flex flex-col gap-2">
                {repartidores.map((repartidor) => (
                  <li
                    key={repartidor.id}
                    className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-borde bg-fondo px-3 py-2"
                  >
                    <div>
                      <p className="font-medium">
                        {repartidor.nombres} {repartidor.apellidos}
                      </p>
                      <p className="text-sm text-texto-suave">{repartidor.celular}</p>
                    </div>
                    <span
                      className={`rounded-full border px-2 py-0.5 text-xs font-medium ${
                        repartidor.pedidos_activos === 0 ? 'border-exito text-exito' : 'border-aviso text-aviso'
                      }`}
                    >
                      {textoEstado(repartidor)}
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </Tarjeta>
        </div>
      )}
    </div>
  )
}
