import { useEffect, useState } from 'react'
import { interpretarError } from '../../api/errores.js'
import { conectarEstadoRepartidores, obtenerEstadoRepartidores } from '../../api/estadoRepartidores.js'
import Alerta from '../../components/ui/Alerta.jsx'
import Boton from '../../components/ui/Boton.jsx'
import Tarjeta from '../../components/ui/Tarjeta.jsx'
import {
  FILTROS,
  claseEstado,
  contarPorEstado,
  filtrarPorEstado,
  nombreCompleto,
  porcentajeAvance,
  textoAvance,
  textoCarga,
} from '../../utils/estadoRepartidores.js'

function PedidoAsignado({ pedido }) {
  const porcentaje = porcentajeAvance(pedido.avance)
  return (
    <li className="flex flex-col gap-2 rounded-lg border border-borde bg-fondo p-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="font-medium">Pedido {pedido.numero_pedido}</p>
        <span className="rounded-full border border-borde px-2 py-0.5 text-xs font-medium">
          {pedido.estado_nombre}
        </span>
      </div>
      {(pedido.entrega_direccion || pedido.entrega_barrio) && (
        <p className="text-sm text-texto-suave">
          {[pedido.entrega_direccion, pedido.entrega_barrio].filter(Boolean).join(' · ')}
        </p>
      )}
      <div>
        <div
          role="progressbar"
          aria-label={`Avance del pedido ${pedido.numero_pedido}`}
          aria-valuemin={0}
          aria-valuemax={100}
          aria-valuenow={porcentaje}
          className="h-2 w-full overflow-hidden rounded-full bg-superficie-alta"
        >
          <div className="h-full bg-marca" style={{ width: `${porcentaje}%` }} />
        </div>
        <p className="mt-1 text-xs text-texto-suave">
          {textoAvance(pedido.avance)}
          {pedido.tiempo_estimado_entrega ? ` · Tiempo estimado: ${pedido.tiempo_estimado_entrega} min` : ''}
        </p>
      </div>
    </li>
  )
}

// HU-37 · Tablero de repartidores de la sede: su estado, su carga y, al seleccionar uno,
// los pedidos que lleva con su avance. Se mantiene al día por WebSocket.
export default function EstadoRepartidores() {
  const [repartidores, setRepartidores] = useState(null) // null mientras carga
  const [error, setError] = useState(null)
  const [enVivo, setEnVivo] = useState(false)
  const [filtro, setFiltro] = useState('todos')
  const [seleccionadoId, setSeleccionadoId] = useState(null)

  useEffect(() => {
    let vigente = true
    let ultimaConsulta = 0

    function cargar() {
      // Si llegan dos avisos juntos, solo se muestra la respuesta más reciente.
      const consulta = ++ultimaConsulta
      obtenerEstadoRepartidores()
        .then((datos) => {
          if (!vigente || consulta !== ultimaConsulta) return
          setRepartidores(datos)
          setError(null)
        })
        .catch((fallo) => {
          if (vigente) setError(interpretarError(fallo).general)
        })
    }

    cargar()
    // El aviso solo dice "algo cambió": se vuelve a pedir la lista.
    const cerrar = conectarEstadoRepartidores({
      alMensaje: cargar,
      alReconectar: cargar,
      alCambiarConexion: (conectado) => {
        if (vigente) setEnVivo(conectado)
      },
    })
    return () => {
      vigente = false
      cerrar()
    }
  }, [])

  const lista = repartidores ?? []
  const conteo = contarPorEstado(lista)
  const visibles = filtrarPorEstado(lista, filtro)
  // Se busca en la lista actual: si el repartidor desaparece, el panel se cierra solo.
  const seleccionado = lista.find((repartidor) => repartidor.id === seleccionadoId) ?? null

  return (
    <div className="flex flex-col gap-4">
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold">Estado de los repartidores</h1>
          <p className="text-texto-suave">
            Supervisa quién está disponible, quién va en una entrega y qué lleva cada uno. Se actualiza solo.
          </p>
        </div>
        <span
          className={`rounded-full border px-2 py-0.5 text-xs font-medium ${
            enVivo ? 'border-exito text-exito' : 'border-borde text-texto-suave'
          }`}
        >
          {enVivo ? 'En vivo' : 'Reconectando…'}
        </span>
      </header>

      {error && <Alerta tipo="error" titulo={error} />}
      {repartidores === null && !error && <p className="text-texto-suave">Cargando…</p>}

      {repartidores !== null && (
        <>
          <div className="flex flex-wrap gap-2" role="group" aria-label="Filtrar por estado">
            {FILTROS.map(({ valor, etiqueta }) => (
              <Boton
                key={valor}
                variante={filtro === valor ? 'primario' : 'secundario'}
                aria-pressed={filtro === valor}
                onClick={() => setFiltro(valor)}
              >
                {etiqueta} ({conteo[valor]})
              </Boton>
            ))}
          </div>

          <div className="grid gap-6 lg:grid-cols-[minmax(0,3fr)_minmax(0,2fr)]">
            <section aria-label="Repartidores">
              {visibles.length === 0 ? (
                <p className="text-texto-suave">
                  {lista.length === 0
                    ? 'No hay repartidores registrados en esta sede.'
                    : 'Ningún repartidor está en este estado ahora.'}
                </p>
              ) : (
                <ul className="grid gap-3 sm:grid-cols-2">
                  {visibles.map((repartidor) => (
                    <li key={repartidor.id}>
                      <button
                        type="button"
                        onClick={() => setSeleccionadoId(repartidor.id)}
                        aria-pressed={seleccionadoId === repartidor.id}
                        className={`flex min-h-11 w-full flex-col gap-2 rounded-xl border bg-superficie p-4 text-left hover:bg-superficie-alta ${
                          seleccionadoId === repartidor.id ? 'border-marca' : 'border-borde'
                        }`}
                      >
                        <div className="flex flex-wrap items-start justify-between gap-2">
                          <div>
                            <p className="font-bold">{nombreCompleto(repartidor)}</p>
                            <p className="text-sm text-texto-suave">{repartidor.celular}</p>
                          </div>
                          <span
                            className={`rounded-full border px-2 py-0.5 text-xs font-medium ${claseEstado(
                              repartidor.estado,
                            )}`}
                          >
                            {repartidor.estado_nombre}
                          </span>
                        </div>
                        <p className="text-sm text-texto-suave">{textoCarga(repartidor.carga)}</p>
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </section>

            <Tarjeta titulo={seleccionado ? `Pedidos de ${nombreCompleto(seleccionado)}` : 'Pedidos asignados'}>
              {!seleccionado && (
                <p className="text-texto-suave">Selecciona un repartidor para ver sus pedidos y su avance.</p>
              )}
              {seleccionado && seleccionado.pedidos.length === 0 && (
                <p className="text-texto-suave">No tiene pedidos asignados.</p>
              )}
              {seleccionado && seleccionado.pedidos.length > 0 && (
                <ul className="flex flex-col gap-3">
                  {seleccionado.pedidos.map((pedido) => (
                    <PedidoAsignado key={pedido.id} pedido={pedido} />
                  ))}
                </ul>
              )}
            </Tarjeta>
          </div>
        </>
      )}
    </div>
  )
}