import { useEffect, useState } from 'react'
import api from '../../api/cliente.js'
import { interpretarError } from '../../api/errores.js'
import { obtenerReporteTiempos } from '../../api/pedidos.js'
import Alerta from '../../components/ui/Alerta.jsx'
import Boton from '../../components/ui/Boton.jsx'
import CampoTexto from '../../components/ui/CampoTexto.jsx'
import Selector from '../../components/ui/Selector.jsx'
import Tarjeta from '../../components/ui/Tarjeta.jsx'
import { anchoBarra, rangoPorDefecto, textoMinutos, validarRango } from '../../utils/reportes.js'

// Pestañas de la página de reportes. La HU-71 (ventas) se agrega aquí como otra entrada.
const REPORTES = [{ valor: 'tiempos', etiqueta: 'Tiempos y desempeño' }]

const DESCRIPCION_FASE = {
  aprobacion: 'De pendiente de aprobación a recibido (solo pedidos web)',
  preparacion: 'De recibido a listo para despacho',
  despacho: 'De listo para despacho a en camino',
  entrega: 'De en camino a entregado',
}

function Cifra({ titulo, valor, detalle }) {
  return (
    <div className="rounded-2xl border border-borde bg-superficie p-4">
      <p className="text-sm text-texto-suave">{titulo}</p>
      <p className="mt-1 font-titulo text-3xl font-bold">{valor}</p>
      {detalle && <p className="mt-1 text-sm text-texto-suave">{detalle}</p>}
    </div>
  )
}

// Barra horizontal de una sola serie: el valor va escrito al lado, el color solo acompaña
function Barra({ etiqueta, valor, maximo, texto }) {
  return (
    <div
      className="h-2.5 overflow-hidden rounded-full bg-superficie-alta"
      role="img"
      aria-label={`${etiqueta}: ${texto}`}
      title={`${etiqueta}: ${texto}`}
    >
      <div className="h-full rounded-full bg-marca" style={{ width: `${anchoBarra(valor, maximo)}%` }} />
    </div>
  )
}

function TiemposPorFase({ fases }) {
  const maximo = Math.max(0, ...fases.map((f) => f.promedio_minutos ?? 0))
  return (
    <Tarjeta titulo="Tiempo promedio por fase">
      <ul className="flex flex-col gap-4">
        {fases.map((fase) => (
          <li key={fase.fase} className="flex flex-col gap-1.5">
            <div className="flex flex-wrap items-baseline justify-between gap-x-3">
              <span className="font-medium">{fase.nombre}</span>
              <span className="font-titulo font-semibold">{textoMinutos(fase.promedio_minutos)}</span>
            </div>
            <Barra
              etiqueta={fase.nombre}
              valor={fase.promedio_minutos}
              maximo={maximo}
              texto={textoMinutos(fase.promedio_minutos)}
            />
            <p className="text-xs text-texto-suave">
              {DESCRIPCION_FASE[fase.fase]} · {fase.pedidos} {fase.pedidos === 1 ? 'pedido' : 'pedidos'}
            </p>
          </li>
        ))}
      </ul>
    </Tarjeta>
  )
}

function DesempenoRepartidores({ repartidores }) {
  const maximo = Math.max(0, ...repartidores.map((r) => r.pedidos_entregados))
  return (
    <Tarjeta titulo="Desempeño de los repartidores">
      {repartidores.length === 0 ? (
        <p className="text-texto-suave">Los pedidos entregados del rango no tienen repartidor asignado.</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full min-w-[34rem] text-left text-sm">
            <thead className="text-texto-suave">
              <tr className="border-b border-borde">
                <th scope="col" className="py-2 pr-3 font-medium">Repartidor</th>
                <th scope="col" className="w-2/5 py-2 pr-3 font-medium">Pedidos entregados</th>
                <th scope="col" className="py-2 pr-3 text-right font-medium">Ciclo promedio</th>
                <th scope="col" className="py-2 text-right font-medium">Reparto promedio</th>
              </tr>
            </thead>
            <tbody>
              {repartidores.map((r) => (
                <tr key={r.id} className="border-b border-borde last:border-0">
                  <td className="py-2.5 pr-3 font-medium">{r.nombre}</td>
                  <td className="py-2.5 pr-3">
                    <div className="flex items-center gap-3">
                      <span className="w-6 text-right tabular-nums">{r.pedidos_entregados}</span>
                      <div className="flex-1">
                        <Barra
                          etiqueta={r.nombre}
                          valor={r.pedidos_entregados}
                          maximo={maximo}
                          texto={`${r.pedidos_entregados} pedidos entregados`}
                        />
                      </div>
                    </div>
                  </td>
                  <td className="py-2.5 pr-3 text-right tabular-nums">{textoMinutos(r.ciclo_promedio_minutos)}</td>
                  <td className="py-2.5 text-right tabular-nums">{textoMinutos(r.reparto_promedio_minutos)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <p className="mt-3 text-xs text-texto-suave">
        Ciclo: desde que se crea el pedido hasta que se entrega. Reparto: desde que está listo para despacho hasta
        que se entrega.
      </p>
    </Tarjeta>
  )
}

// HU-72 · Tiempos promedio por fase y desempeño de los repartidores
function ReporteTiempos({ sedes }) {
  const [filtros, setFiltros] = useState(() => ({ ...rangoPorDefecto(), sede: '' }))
  const [consulta, setConsulta] = useState(filtros)
  const [datos, setDatos] = useState(null)
  const [error, setError] = useState(null)
  const [errorRango, setErrorRango] = useState(null)
  const [consultaCargada, setConsultaCargada] = useState(null)

  useEffect(() => {
    let vigente = true
    obtenerReporteTiempos(consulta)
      .then((respuesta) => {
        if (!vigente) return
        setDatos(respuesta)
        setError(null)
      })
      .catch((fallo) => {
        if (!vigente) return
        const { general, campos } = interpretarError(fallo)
        setError(general ?? Object.values(campos)[0] ?? 'No se pudo generar el reporte.')
        setDatos(null)
      })
      .finally(() => vigente && setConsultaCargada(consulta))
    return () => {
      vigente = false
    }
  }, [consulta])

  function cambiar(campo) {
    return (e) => {
      setFiltros((actual) => ({ ...actual, [campo]: e.target.value }))
      setErrorRango(null)
    }
  }

  function consultar(e) {
    e.preventDefault()
    const problema = validarRango(filtros.desde, filtros.hasta)
    setErrorRango(problema)
    if (!problema) setConsulta({ ...filtros })
  }

  const cargando = consultaCargada !== consulta

  return (
    <div className="flex flex-col gap-6">
      <form onSubmit={consultar} noValidate className="flex flex-wrap items-start gap-3">
        <CampoTexto
          etiqueta="Desde"
          type="date"
          className="w-40 sm:w-44"
          value={filtros.desde}
          max={filtros.hasta || undefined}
          onChange={cambiar('desde')}
          error={errorRango}
        />
        <CampoTexto
          etiqueta="Hasta"
          type="date"
          className="w-40 sm:w-44"
          value={filtros.hasta}
          onChange={cambiar('hasta')}
        />
        <Selector
          etiqueta="Sede"
          name="sede"
          value={filtros.sede}
          onChange={cambiar('sede')}
          opciones={sedes.map((s) => ({ valor: String(s.id), etiqueta: s.nombre }))}
          textoVacio="Todas las sedes"
        />
        <Boton tipo="submit" className="sm:mt-7" disabled={cargando}>
          {cargando ? 'Generando…' : 'Generar reporte'}
        </Boton>
      </form>

      {error && <Alerta tipo="error" titulo={error} />}

      {datos?.sin_datos && (
        <Alerta tipo="info" titulo={datos.mensaje}>
          Prueba con un rango más amplio u otra sede. Solo cuentan los pedidos con estado final «Entregado».
        </Alerta>
      )}

      {datos && !datos.sin_datos && (
        <>
          <section aria-label="Resumen" className="grid gap-4 sm:grid-cols-2">
            <Cifra
              titulo="Pedidos entregados"
              valor={datos.pedidos_entregados}
              detalle={datos.sede ? datos.sede.nombre : 'Todas las sedes'}
            />
            <Cifra
              titulo="Ciclo promedio"
              valor={textoMinutos(datos.ciclo_promedio_minutos)}
              detalle="Desde que se crea el pedido hasta la entrega"
            />
          </section>
          <div className="grid gap-4 lg:grid-cols-[2fr_3fr] [&>*]:min-w-0">
            <TiemposPorFase fases={datos.fases} />
            <DesempenoRepartidores repartidores={datos.repartidores} />
          </div>
        </>
      )}
    </div>
  )
}

export default function Reportes() {
  const [reporte, setReporte] = useState(REPORTES[0].valor)
  const [sedes, setSedes] = useState([])

  useEffect(() => {
    api
      .get('/sedes/')
      .then(({ data }) => setSedes(Array.isArray(data) ? data : (data.results ?? [])))
      .catch(() => setSedes([]))
  }, [])

  return (
    <div className="flex flex-col gap-6">
      <header>
        <h1 className="text-2xl font-bold">Reportes</h1>
        <p className="text-texto-suave">Consulta cómo va el negocio en el rango de fechas que elijas.</p>
      </header>

      {REPORTES.length > 1 && (
        <div role="tablist" aria-label="Tipo de reporte" className="flex flex-wrap gap-2">
          {REPORTES.map((r) => (
            <button
              key={r.valor}
              type="button"
              role="tab"
              aria-selected={reporte === r.valor}
              onClick={() => setReporte(r.valor)}
              className={`rounded-full px-4 py-2 text-sm font-medium ${
                reporte === r.valor ? 'bg-marca text-sobre-marca' : 'bg-superficie-alta text-texto hover:bg-borde'
              }`}
            >
              {r.etiqueta}
            </button>
          ))}
        </div>
      )}

      {reporte === 'tiempos' && <ReporteTiempos sedes={sedes} />}
    </div>
  )
}
