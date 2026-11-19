import { useEffect, useState } from 'react'
import { interpretarError } from '../../api/errores.js'
import { obtenerReporteVentas } from '../../api/pedidos.js'
import { formatearPrecio } from '../../utils/formato.js'
import {
  AGRUPACIONES_VENTAS,
  cuentaUnidades,
  filasConciliacion,
  rangoPorDefecto,
  validarRango,
} from '../../utils/reportes.js'
import Alerta from '../ui/Alerta.jsx'
import Boton from '../ui/Boton.jsx'
import CampoTexto from '../ui/CampoTexto.jsx'
import Selector from '../ui/Selector.jsx'
import Tarjeta from '../ui/Tarjeta.jsx'
import Barra from './Barra.jsx'
import Cifra from './Cifra.jsx'

function TablaVentas({ datos }) {
  const etiquetaGrupo = AGRUPACIONES_VENTAS.find((a) => a.valor === datos.agrupar)?.etiqueta ?? 'Grupo'
  const conUnidades = cuentaUnidades(datos.agrupar)
  const maximo = Math.max(0, ...datos.grupos.map((g) => Number(g.ventas)))

  return (
    <Tarjeta titulo={`Ventas por ${etiquetaGrupo.toLowerCase()}`}>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[34rem] text-left text-sm">
          <thead className="text-texto-suave">
            <tr className="border-b border-borde">
              <th scope="col" className="py-2 pr-3 font-medium">{etiquetaGrupo}</th>
              {conUnidades && <th scope="col" className="py-2 pr-3 text-right font-medium">Unidades</th>}
              <th scope="col" className="py-2 pr-3 text-right font-medium">Pedidos</th>
              <th scope="col" className="py-2 pr-3 text-right font-medium">Ventas</th>
              <th scope="col" className="w-1/4 py-2 font-medium">Participación</th>
            </tr>
          </thead>
          <tbody>
            {datos.grupos.map((g) => (
              <tr key={g.clave} className="border-b border-borde last:border-0">
                <td className="py-2.5 pr-3 font-medium">{g.nombre}</td>
                {conUnidades && <td className="py-2.5 pr-3 text-right tabular-nums">{g.unidades}</td>}
                <td className="py-2.5 pr-3 text-right tabular-nums">{g.pedidos}</td>
                <td className="py-2.5 pr-3 text-right tabular-nums">{formatearPrecio(g.ventas)}</td>
                <td className="py-2.5">
                  <div className="flex items-center gap-3">
                    <span className="w-12 text-right tabular-nums">{g.porcentaje.replace('.', ',')} %</span>
                    <div className="flex-1">
                      <Barra
                        etiqueta={g.nombre}
                        valor={Number(g.ventas)}
                        maximo={maximo}
                        texto={`${formatearPrecio(g.ventas)} (${g.porcentaje} %)`}
                      />
                    </div>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Tarjeta>
  )
}

// Por producto o categoría las líneas no incluyen descuentos ni domicilios: aquí cuadra con lo facturado
function Conciliacion({ conciliacion }) {
  const filas = filasConciliacion(conciliacion)
  if (filas.length === 0) return null
  return (
    <Tarjeta titulo="De las ventas por producto al total facturado">
      <dl className="flex flex-col gap-2 text-sm">
        {filas.map((f) => (
          <div
            key={f.etiqueta}
            className={`flex justify-between gap-3 ${f.total ? 'border-t border-borde pt-2 font-semibold' : ''}`}
          >
            <dt>
              <span className="inline-block w-4 text-texto-suave" aria-hidden="true">{f.signo}</span>
              {f.etiqueta}
            </dt>
            <dd className="tabular-nums">{formatearPrecio(f.valor)}</dd>
          </div>
        ))}
      </dl>
      <p className="mt-3 text-xs text-texto-suave">
        El descuento y el domicilio son del pedido completo, no de un producto, por eso se suman aparte.
      </p>
    </Tarjeta>
  )
}

// HU-71 · Ventas agrupadas por producto, categoría, sede o zona en un rango de fechas
export default function ReporteVentas({ sedes }) {
  const [filtros, setFiltros] = useState(() => ({ ...rangoPorDefecto(), agrupar: 'producto', sede: '' }))
  const [consulta, setConsulta] = useState(filtros)
  const [datos, setDatos] = useState(null)
  const [error, setError] = useState(null)
  const [errorRango, setErrorRango] = useState(null)
  const [consultaCargada, setConsultaCargada] = useState(null)

  useEffect(() => {
    let vigente = true
    obtenerReporteVentas(consulta)
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
          etiqueta="Agrupar por"
          name="agrupar"
          value={filtros.agrupar}
          onChange={cambiar('agrupar')}
          opciones={AGRUPACIONES_VENTAS}
          sinOpcionVacia
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

      {/* Criterio 4: sin ventas se avisa en lugar de pintar la tabla */}
      {datos?.sin_datos && (
        <Alerta tipo="info" titulo={datos.mensaje}>
          Prueba con un rango más amplio u otra sede. Solo cuentan los pedidos no cancelados.
        </Alerta>
      )}

      {datos && !datos.sin_datos && (
        <>
          <section aria-label="Resumen" className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <Cifra
              titulo="Total facturado"
              valor={formatearPrecio(datos.totales.total)}
              detalle={datos.sede ? datos.sede.nombre : 'Todas las sedes'}
            />
            <Cifra titulo="Pedidos" valor={datos.totales.pedidos} detalle="No cancelados" />
            <Cifra titulo="Ticket promedio" valor={formatearPrecio(datos.totales.ticket_promedio)} />
            <Cifra
              titulo="Descuentos"
              valor={formatearPrecio(datos.totales.descuentos)}
              detalle={`Domicilios: ${formatearPrecio(datos.totales.domicilio)}`}
            />
          </section>
          <div className={`grid gap-4 [&>*]:min-w-0 ${datos.conciliacion ? 'lg:grid-cols-[3fr_2fr]' : ''}`}>
            <TablaVentas datos={datos} />
            <Conciliacion conciliacion={datos.conciliacion} />
          </div>
        </>
      )}
    </div>
  )
}
