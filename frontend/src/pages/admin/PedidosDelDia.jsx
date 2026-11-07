import { useEffect, useState } from 'react'
import { interpretarError } from '../../api/errores.js'
import { obtenerResumenDia } from '../../api/pedidos.js'
import { ROLES } from '../../auth/roles.js'
import { useAuth } from '../../auth/useAuth.js'
import Alerta from '../../components/ui/Alerta.jsx'
import Boton from '../../components/ui/Boton.jsx'
import Selector from '../../components/ui/Selector.jsx'
import Tarjeta from '../../components/ui/Tarjeta.jsx'
import { FASES_PEDIDO, datosEstado, pedidosActivos } from '../../utils/estadosPedido.js'
import { horaCorta } from '../../utils/tiempo.js'

// how often the summary asks the server for changes
const INTERVALO_MS = 30000

function Contador({ estado, cantidad }) {
  const { etiqueta, clases } = datosEstado(estado)
  return (
    <li className={`flex flex-col rounded-lg border px-3 py-2 ${cantidad > 0 ? clases : 'border-borde text-texto-suave'}`}>
      <span className="text-2xl font-bold">{cantidad}</span>
      <span className="text-sm">{etiqueta}</span>
    </li>
  )
}

function ResumenSede({ sede }) {
  return (
    <Tarjeta>
      <div className="mb-4 flex flex-wrap items-end justify-between gap-2">
        <h2 className="text-lg font-bold">{sede.nombre}</h2>
        <p className="text-sm text-texto-suave">
          <span className="text-2xl font-bold text-texto">{sede.total}</span> pedidos hoy ·{' '}
          {pedidosActivos(sede.por_estado)} en curso
        </p>
      </div>
      <div className="flex flex-col gap-4">
        {FASES_PEDIDO.map((fase) => (
          <section key={fase.titulo} aria-label={fase.titulo}>
            <h3 className="mb-2 text-sm font-bold uppercase tracking-wide text-texto-suave">{fase.titulo}</h3>
            <ul className="grid grid-cols-2 gap-2 sm:grid-cols-3">
              {fase.estados.map((estado) => (
                <Contador key={estado} estado={estado} cantidad={sede.por_estado[estado] ?? 0} />
              ))}
            </ul>
          </section>
        ))}
      </div>
    </Tarjeta>
  )
}

// HU-67 · Orders of the day by sede, with a counter for every state of the flow.
// The operator sees his sede; the administrator sees every active sede and can pick one
export default function PedidosDelDia() {
  const { usuario } = useAuth()
  const esAdministrador = usuario?.rol === ROLES.ADMINISTRADOR
  const [resumen, setResumen] = useState(null)
  const [error, setError] = useState(null)
  const [actualizado, setActualizado] = useState(null)
  const [recarga, setRecarga] = useState(0) // bump it to load again
  const [sedeElegida, setSedeElegida] = useState('')

  useEffect(() => {
    let vigente = true

    function cargar() {
      obtenerResumenDia()
        .then((datos) => {
          if (!vigente) return
          setResumen(datos)
          setError(null)
          setActualizado(new Date())
        })
        .catch((fallo) => {
          if (vigente) setError(interpretarError(fallo).general)
        })
    }

    cargar()
    const temporizador = setInterval(cargar, INTERVALO_MS)
    return () => {
      vigente = false
      clearInterval(temporizador)
    }
  }, [recarga])

  const sedes = resumen?.sedes ?? []
  const visibles = sedeElegida ? sedes.filter((sede) => String(sede.sede_id) === sedeElegida) : sedes

  return (
    <div className="flex flex-col gap-4">
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold">Pedidos del día</h1>
          <p className="text-texto-suave">
            {actualizado
              ? `Actualizado a las ${horaCorta(actualizado)} · Se actualiza solo cada ${INTERVALO_MS / 1000} segundos`
              : 'Cargando…'}
          </p>
        </div>
        <Boton variante="secundario" onClick={() => setRecarga((numero) => numero + 1)}>
          Actualizar ahora
        </Boton>
      </header>

      {esAdministrador && sedes.length > 1 && (
        <Selector
          etiqueta="Sede"
          textoVacio="Todas las sedes"
          value={sedeElegida}
          onChange={(evento) => setSedeElegida(evento.target.value)}
          opciones={sedes.map((sede) => ({ valor: String(sede.sede_id), etiqueta: sede.nombre }))}
          className="max-w-xs"
        />
      )}

      {error && <Alerta tipo="error" titulo={error} />}
      {resumen && sedes.length === 0 && (
        <Alerta tipo="info" titulo="No hay sedes para mostrar">
          Tu cuenta no tiene una sede asignada.
        </Alerta>
      )}
      {visibles.map((sede) => (
        <ResumenSede key={sede.sede_id} sede={sede} />
      ))}
    </div>
  )
}
