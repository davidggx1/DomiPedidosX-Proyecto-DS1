import { useEffect, useState } from 'react'
import { interpretarError } from '../../api/errores.js'
import { obtenerHistorialEntregas } from '../../api/repartidores.js'
import Alerta from '../../components/ui/Alerta.jsx'
import Boton from '../../components/ui/Boton.jsx'
import CampoTexto from '../../components/ui/CampoTexto.jsx'
import Tarjeta from '../../components/ui/Tarjeta.jsx'
import { formatearPrecio } from '../../utils/formato.js'
import { agruparPorDia, atajosFecha, nombreDia } from '../../utils/historialEntregas.js'
import { validarRango } from '../../utils/reportes.js'
import { horaCorta } from '../../utils/tiempo.js'

function Cifra({ titulo, valor, detalle }) {
  return (
    <div className="rounded-2xl border border-borde bg-superficie p-4">
      <p className="text-sm text-texto-suave">{titulo}</p>
      <p className="mt-1 font-titulo text-2xl font-bold">{valor}</p>
      {detalle && <p className="mt-1 text-sm text-texto-suave">{detalle}</p>}
    </div>
  )
}

function FilaEntrega({ entrega }) {
  const efectivo = entrega.metodo_pago === 'efectivo'
  return (
    <li className="flex flex-col gap-1 rounded-xl border border-borde bg-fondo p-3">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <p className="font-bold">{entrega.numero_pedido}</p>
        <p className="text-sm text-texto-suave">Entregado a las {horaCorta(entrega.entregado_en)}</p>
      </div>
      <p className="text-sm">
        {[entrega.cliente, entrega.entrega_barrio].filter(Boolean).join(' · ') || 'Sin datos del cliente'}
      </p>
      <div className="flex flex-wrap items-baseline justify-between gap-2 text-sm">
        <span className="font-semibold">{entrega.total ? formatearPrecio(entrega.total) : '—'}</span>
        <span className="text-texto-suave">{entrega.metodo_pago_nombre ?? 'Sin factura'}</span>
      </div>
      {efectivo && entrega.monto_recaudado && (
        <p className="text-sm text-texto-suave">
          Recibiste {formatearPrecio(entrega.monto_recaudado)} · cambio {formatearPrecio(entrega.cambio)}
        </p>
      )}
    </li>
  )
}

// HU-46 · Entregas que hizo el repartidor por día, con el dinero cobrado
export default function HistorialEntregas() {
  const [atajos] = useState(() => atajosFecha())
  const [filtros, setFiltros] = useState({ desde: atajos[0].desde, hasta: atajos[0].hasta })
  const [consulta, setConsulta] = useState(filtros)
  const [consultaCargada, setConsultaCargada] = useState(null)
  const [datos, setDatos] = useState(null)
  const [error, setError] = useState(null)
  const [errorRango, setErrorRango] = useState(null)

  useEffect(() => {
    let vigente = true
    obtenerHistorialEntregas(consulta)
      .then((respuesta) => {
        if (!vigente) return
        setDatos(respuesta)
        setError(null)
      })
      .catch((fallo) => {
        if (!vigente) return
        const { general, campos } = interpretarError(fallo)
        setError(general ?? Object.values(campos)[0] ?? 'No se pudo cargar el historial.')
        setDatos(null)
      })
      .finally(() => vigente && setConsultaCargada(consulta))
    return () => {
      vigente = false
    }
  }, [consulta])

  function consultar(evento) {
    evento.preventDefault()
    const problema = validarRango(filtros.desde, filtros.hasta)
    setErrorRango(problema)
    if (!problema) setConsulta({ ...filtros })
  }

  function usarAtajo(atajo) {
    const rango = { desde: atajo.desde, hasta: atajo.hasta }
    setFiltros(rango)
    setErrorRango(null)
    setConsulta(rango)
  }

  function cambiar(campo) {
    return (evento) => {
      setFiltros((actuales) => ({ ...actuales, [campo]: evento.target.value }))
      setErrorRango(null)
    }
  }

  const cargando = consultaCargada !== consulta
  const resumen = datos?.resumen
  const grupos = datos ? agruparPorDia(datos.entregas) : []

  return (
    <div className="flex flex-col gap-5">
      <header>
        <h1 className="text-2xl font-bold">Historial de entregas</h1>
        <p className="text-texto-suave">Tus pedidos entregados y el dinero que cobraste.</p>
      </header>

      <div className="flex flex-wrap gap-2" role="group" aria-label="Rangos rápidos">
        {atajos.map((atajo) => {
          const activo = consulta.desde === atajo.desde && consulta.hasta === atajo.hasta
          return (
            <button
              key={atajo.etiqueta}
              type="button"
              aria-pressed={activo}
              onClick={() => usarAtajo(atajo)}
              className={`rounded-full px-4 py-2 text-sm font-medium ${
                activo ? 'bg-marca text-sobre-marca' : 'bg-superficie-alta text-texto hover:bg-borde'
              }`}
            >
              {atajo.etiqueta}
            </button>
          )
        })}
      </div>

      <form onSubmit={consultar} noValidate className="flex flex-wrap items-start gap-3">
        <CampoTexto
          etiqueta="Desde"
          type="date"
          className="w-40"
          value={filtros.desde}
          max={filtros.hasta || undefined}
          onChange={cambiar('desde')}
          error={errorRango}
        />
        <CampoTexto etiqueta="Hasta" type="date" className="w-40" value={filtros.hasta} onChange={cambiar('hasta')} />
        <Boton tipo="submit" variante="secundario" className="sm:mt-7" disabled={cargando}>
          Consultar
        </Boton>
      </form>

      {error && <Alerta tipo="error" titulo={error} />}
      {cargando && !datos && <p className="text-texto-suave">Cargando…</p>}

      {resumen && (
        <section aria-label="Resumen" className="grid gap-3 sm:grid-cols-3">
          <Cifra titulo="Entregas" valor={resumen.entregas} />
          <Cifra
            titulo="Efectivo cobrado"
            valor={formatearPrecio(resumen.efectivo_cobrado)}
            detalle={`${resumen.pedidos_efectivo} ${resumen.pedidos_efectivo === 1 ? 'pedido' : 'pedidos'} · para entregar en la sede`}
          />
          <Cifra
            titulo="Pagado en línea"
            valor={formatearPrecio(resumen.pagado_en_linea)}
            detalle={`${resumen.pedidos_en_linea} ${resumen.pedidos_en_linea === 1 ? 'pedido' : 'pedidos'} con tarjeta o transferencia`}
          />
        </section>
      )}

      {datos && datos.entregas.length === 0 && (
        <Alerta tipo="info" titulo="No hiciste entregas en estas fechas." />
      )}

      {grupos.map((grupo) => (
        <Tarjeta key={grupo.dia} titulo={`${nombreDia(grupo.dia)} · ${grupo.entregas.length} ${grupo.entregas.length === 1 ? 'entrega' : 'entregas'}`}>
          <ul className="flex flex-col gap-3">
            {grupo.entregas.map((entrega) => (
              <FilaEntrega key={entrega.id} entrega={entrega} />
            ))}
          </ul>
        </Tarjeta>
      ))}
    </div>
  )
}
