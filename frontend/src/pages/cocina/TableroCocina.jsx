import { useEffect, useState } from 'react'
import { interpretarError } from '../../api/errores.js'
import { cambiarEstadoPedido, obtenerTableroCocina } from '../../api/pedidos.js'
import TarjetaPedido from '../../components/cocina/TarjetaPedido.jsx'
import Alerta from '../../components/ui/Alerta.jsx'
import Boton from '../../components/ui/Boton.jsx'
import { AVANCE_COCINA, COLUMNAS_COCINA } from '../../utils/cocina.js'

// how often the board asks the server for changes
const INTERVALO_MS = 10000

// HU-29, HU-30 y HU-31 · Kitchen board with three columns
export default function TableroCocina() {
  const [tablero, setTablero] = useState(null)
  const [cargando, setCargando] = useState(true)
  const [errorCarga, setErrorCarga] = useState(null)
  const [recarga, setRecarga] = useState(0) // bump it to load the board again
  const [ahora, setAhora] = useState(() => Date.now())
  const [moviendo, setMoviendo] = useState(null) // id of the order being moved
  const [mensaje, setMensaje] = useState(null)

  useEffect(() => {
    let vigente = true

    function cargar() {
      obtenerTableroCocina()
        .then((datos) => {
          if (!vigente) return
          setTablero(datos)
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

  async function avanzar(tarjeta) {
    const { estado, texto } = AVANCE_COCINA[tarjeta.estado]
    setMoviendo(tarjeta.id)
    setMensaje(null)
    try {
      await cambiarEstadoPedido(tarjeta.id, estado)
      setMensaje({ tipo: 'exito', texto: `${tarjeta.numero_pedido}: ${texto.toLowerCase()}.` })
    } catch (error) {
      // if somebody else already moved it, the board shows the real state
      setMensaje({ tipo: 'error', texto: interpretarError(error).general })
    } finally {
      setMoviendo(null)
      setRecarga((numero) => numero + 1)
    }
  }

  return (
    <div className="flex flex-col gap-4">
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold">Tablero de cocina</h1>
          <p className="text-texto-suave">
            Se actualiza solo cada {INTERVALO_MS / 1000} segundos.
          </p>
        </div>
        <Boton variante="secundario" onClick={() => setRecarga((numero) => numero + 1)}>
          Actualizar ahora
        </Boton>
      </header>

      {mensaje && <Alerta tipo={mensaje.tipo} titulo={mensaje.texto} />}
      {errorCarga && <Alerta tipo="error" titulo={errorCarga} />}
      {cargando && <p className="text-texto-suave">Cargando pedidos…</p>}

      {tablero && (
        <div className="grid gap-4 md:grid-cols-3">
          {COLUMNAS_COCINA.map(({ estado, titulo }) => {
            const tarjetas = tablero[estado] ?? []
            return (
              <section
                key={estado}
                aria-label={`${titulo}: ${tarjetas.length} pedidos`}
                className="flex flex-col gap-3 rounded-xl border border-borde bg-superficie p-3"
              >
                <h2 className="flex items-center justify-between text-lg font-bold">
                  {titulo}
                  <span className="rounded-full border border-borde px-2 py-0.5 text-sm font-medium">
                    {tarjetas.length}
                  </span>
                </h2>
                {tarjetas.length === 0 ? (
                  <p className="text-sm text-texto-suave">Sin pedidos.</p>
                ) : (
                  <ul className="flex flex-col gap-3">
                    {tarjetas.map((tarjeta) => (
                      <TarjetaPedido
                        key={tarjeta.id}
                        tarjeta={tarjeta}
                        ahora={ahora}
                        ocupada={moviendo === tarjeta.id}
                        alAvanzar={avanzar}
                      />
                    ))}
                  </ul>
                )}
              </section>
            )
          })}
        </div>
      )}
    </div>
  )
}
