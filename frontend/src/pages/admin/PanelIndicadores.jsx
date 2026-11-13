import { useEffect, useState } from 'react'
import { interpretarError } from '../../api/errores.js'
import { obtenerIndicadoresDia } from '../../api/pedidos.js'
import Alerta from '../../components/ui/Alerta.jsx'
import Boton from '../../components/ui/Boton.jsx'
import Selector from '../../components/ui/Selector.jsx'
import Tarjeta from '../../components/ui/Tarjeta.jsx'
import { formatearPrecio } from '../../utils/formato.js'
import {
  INTERVALO_INDICADORES_MS,
  nivelOcupacion,
  porcentajeCancelados,
  textoTiempoEntrega,
} from '../../utils/indicadores.js'
import { horaCorta } from '../../utils/tiempo.js'

const COLOR_BARRA = {
  normal: 'bg-exito',
  alerta: 'bg-aviso',
  saturada: 'bg-error',
  sin_franja: 'bg-borde',
}

function Indicador({ titulo, valor, detalle, destacado = false }) {
  return (
    <div
      className={`rounded-2xl border p-4 ${destacado ? 'border-marca/40 bg-marca/10' : 'border-borde bg-superficie'}`}
    >
      <p className="text-sm text-texto-suave">{titulo}</p>
      <p className="mt-1 font-titulo text-3xl font-bold">{valor}</p>
      {detalle && <p className="mt-1 text-sm text-texto-suave">{detalle}</p>}
    </div>
  )
}

function OcupacionSede({ sede }) {
  const { ocupacion } = sede
  const nivel = nivelOcupacion(ocupacion)
  const sinFranja = nivel === 'sin_franja'
  const ancho = sinFranja ? 0 : Math.min(ocupacion.porcentaje, 100)

  return (
    <li className="flex flex-col gap-1">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <span className="font-medium">{sede.nombre}</span>
        <span className="text-sm text-texto-suave">
          {sinFranja
            ? `${ocupacion.activos} en cocina · sin franja configurada ahora`
            : `${ocupacion.activos} de ${ocupacion.maximo} pedidos · ${ocupacion.porcentaje} %`}
        </span>
      </div>
      <div
        role="progressbar"
        aria-label={`Ocupación de la cocina de ${sede.nombre}`}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={sinFranja ? undefined : ocupacion.porcentaje}
        className="h-3 overflow-hidden rounded-full bg-superficie-alta"
      >
        <div className={`h-full rounded-full transition-all ${COLOR_BARRA[nivel]}`} style={{ width: `${ancho}%` }} />
      </div>
    </li>
  )
}

// HU-70 · Panel de indicadores del día (inicio del administrador).
// Consolidado de todas las sedes o una sola; se actualiza solo cada minuto.
export default function PanelIndicadores() {
  const [sede, setSede] = useState('')
  const [opcionesSede, setOpcionesSede] = useState([])
  const [datos, setDatos] = useState(null)
  const [error, setError] = useState(null)
  const [actualizado, setActualizado] = useState(null)
  const [recarga, setRecarga] = useState(0)

  useEffect(() => {
    let vigente = true
    function cargar() {
      obtenerIndicadoresDia(sede)
        .then((respuesta) => {
          if (!vigente) return
          setDatos(respuesta)
          setError(null)
          setActualizado(new Date())
          // Las opciones del selector salen del consolidado, que trae todas las sedes activas.
          if (!sede) setOpcionesSede(respuesta.sedes.map((s) => ({ valor: String(s.sede_id), etiqueta: s.nombre })))
        })
        .catch((fallo) => vigente && setError(interpretarError(fallo).general))
    }
    cargar()
    const temporizador = setInterval(cargar, INTERVALO_INDICADORES_MS)
    return () => {
      vigente = false
      clearInterval(temporizador)
    }
  }, [sede, recarga])

  const tiempo = datos ? textoTiempoEntrega(datos.tiempo_promedio_entrega, datos.entregados) : null

  return (
    <div className="flex flex-col gap-6">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold">Indicadores del día</h1>
          <p className="text-texto-suave">
            {actualizado ? `Actualizado a las ${horaCorta(actualizado)} · se actualiza solo cada minuto` : 'Cargando…'}
          </p>
        </div>
        <div className="flex flex-wrap items-end gap-3">
          <Selector
            etiqueta="Ver"
            name="sede"
            value={sede}
            onChange={(evento) => setSede(evento.target.value)}
            opciones={opcionesSede}
            textoVacio="Todas las sedes"
          />
          <Boton variante="secundario" onClick={() => setRecarga((n) => n + 1)}>
            Actualizar ahora
          </Boton>
        </div>
      </header>

      {error && <Alerta tipo="error" titulo={error} />}

      {datos && (
        <>
          <section aria-label="Indicadores" className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <Indicador titulo="Pedidos de hoy" valor={datos.pedidos} destacado />
            <Indicador titulo="Ventas" valor={formatearPrecio(datos.ventas)} detalle="Sin contar los cancelados" />
            <Indicador titulo="Tiempo promedio de entrega" valor={tiempo.valor} detalle={tiempo.detalle} />
            <Indicador
              titulo="Cancelaciones"
              valor={datos.cancelaciones}
              detalle={`${porcentajeCancelados(datos.cancelaciones, datos.pedidos)} % de los pedidos`}
            />
          </section>

          <Tarjeta titulo="Ocupación de cocina">
            {datos.sedes.length === 0 ? (
              <p className="text-texto-suave">No hay sedes activas.</p>
            ) : (
              <ul className="flex flex-col gap-4">
                {datos.sedes.map((s) => (
                  <OcupacionSede key={s.sede_id} sede={s} />
                ))}
              </ul>
            )}
          </Tarjeta>

          {datos.sedes.length > 1 && (
            <Tarjeta titulo="Por sede">
              <div className="overflow-x-auto">
                <table className="w-full min-w-[36rem] text-left text-sm">
                  <thead className="text-texto-suave">
                    <tr className="border-b border-borde">
                      <th scope="col" className="py-2 pr-3 font-medium">Sede</th>
                      <th scope="col" className="py-2 pr-3 text-right font-medium">Pedidos</th>
                      <th scope="col" className="py-2 pr-3 text-right font-medium">Ventas</th>
                      <th scope="col" className="py-2 pr-3 text-right font-medium">Entrega promedio</th>
                      <th scope="col" className="py-2 text-right font-medium">Cancelaciones</th>
                    </tr>
                  </thead>
                  <tbody>
                    {datos.sedes.map((s) => (
                      <tr key={s.sede_id} className="border-b border-borde last:border-0">
                        <td className="py-2 pr-3 font-medium">{s.nombre}</td>
                        <td className="py-2 pr-3 text-right">{s.pedidos}</td>
                        <td className="py-2 pr-3 text-right">{formatearPrecio(s.ventas)}</td>
                        <td className="py-2 pr-3 text-right">{s.entregados ? `${s.tiempo_promedio_entrega} min` : '—'}</td>
                        <td className="py-2 text-right">{s.cancelaciones}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </Tarjeta>
          )}
        </>
      )}
    </div>
  )
}
