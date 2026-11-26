import { useEffect, useState } from 'react'
import { interpretarError } from '../../api/errores.js'
import { obtenerReporteDemanda } from '../../api/pedidos.js'
import { formatearPrecio } from '../../utils/formato.js'
import {
  DIAS_CORTOS,
  MEDIDAS_DEMANDA,
  intensidadCelda,
  rangoPorDefecto,
  textoFechasCortas,
  textoHora,
  validarRango,
} from '../../utils/reportes.js'
import Alerta from '../ui/Alerta.jsx'
import Boton from '../ui/Boton.jsx'
import CampoTexto from '../ui/CampoTexto.jsx'
import Selector from '../ui/Selector.jsx'
import Tarjeta from '../ui/Tarjeta.jsx'
import Barra from './Barra.jsx'
import BotonExportar from './BotonExportar.jsx'
import Cifra from './Cifra.jsx'

const HORAS = Array.from({ length: 24 }, (_, hora) => hora)

// Color de una celda: el rojo de la marca mezclado con transparente según la intensidad (0 a 1)
function colorCelda(intensidad) {
  return intensidad
    ? { backgroundColor: `color-mix(in srgb, var(--color-marca) ${Math.round(intensidad * 100)}%, transparent)` }
    : undefined
}

// HU-73 · Columnas del CSV: una fila por celda (día y hora) con su demanda.
// "Fechas" dice de qué días salieron los pedidos (una celda suma todos los viernes del rango)
const COLUMNAS_CSV_CELDAS = [
  { titulo: 'Día', valor: (c) => DIAS_CORTOS[c.dia] },
  { titulo: 'Hora', valor: (c) => textoHora(c.hora) },
  { titulo: 'Pedidos', valor: (c) => c.pedidos },
  { titulo: 'Ventas', valor: (c) => c.ventas },
  { titulo: 'Fechas', valor: (c) => c.fechas.join('; ') },
]

function textoMedida(valor, medida) {
  return medida === 'ventas' ? formatearPrecio(valor) : `${valor} ${Number(valor) === 1 ? 'pedido' : 'pedidos'}`
}

// Mapa de calor: 7 filas (días) × 24 columnas (horas). La intensidad del rojo es la demanda;
// el valor exacto va en el título de cada celda (y para lectores de pantalla)
function MapaDeCalor({ datos, medida }) {
  const maximo = Math.max(0, ...datos.celdas.map((c) => Number(c[medida])))
  const porDia = Object.keys(DIAS_CORTOS).map((dia) => ({
    dia: Number(dia),
    celdas: datos.celdas.filter((c) => c.dia === Number(dia)),
  }))

  return (
    <div className="overflow-x-auto">
      <div
        className="grid min-w-[44rem] gap-1 text-xs"
        style={{ gridTemplateColumns: '2.5rem repeat(24, minmax(0, 1fr))' }}
        role="table"
        aria-label={`Mapa de calor de ${medida} por día y hora`}
      >
        <div role="row" className="contents">
          <span role="columnheader" />
          {HORAS.map((hora) => (
            <span key={hora} role="columnheader" className="text-center text-texto-suave tabular-nums">
              {hora % 3 === 0 ? hora : ''}
            </span>
          ))}
        </div>
        {porDia.map(({ dia, celdas }) => (
          <div key={dia} role="row" className="contents">
            <span role="rowheader" className="self-center font-medium text-texto-suave">
              {DIAS_CORTOS[dia]}
            </span>
            {celdas.map((celda) => {
              const intensidad = intensidadCelda(celda[medida], maximo)
              const fechas = textoFechasCortas(celda.fechas)
              const texto = `${DIAS_CORTOS[dia]} ${textoHora(celda.hora)}: ${textoMedida(celda[medida], medida)}${
                fechas ? ` (${fechas})` : ''
              }`
              return (
                <div
                  key={celda.hora}
                  role="cell"
                  aria-label={texto}
                  title={texto}
                  className="aspect-square rounded-sm bg-superficie-alta"
                  style={colorCelda(intensidad)}
                />
              )
            })}
          </div>
        ))}
      </div>
      <div className="mt-3 flex items-center gap-2 text-xs text-texto-suave">
        <span>Menos</span>
        {[0, 0.25, 0.5, 0.75, 1].map((nivel) => (
          <span
            key={nivel}
            className="h-3 w-5 rounded-sm bg-superficie-alta"
            style={colorCelda(nivel)}
          />
        ))}
        <span>Más</span>
      </div>
    </div>
  )
}

// Gráfico de barras horizontales (por día o por hora) con el valor escrito al lado
function GraficoBarras({ titulo, filas, etiqueta, medida }) {
  const maximo = Math.max(0, ...filas.map((f) => Number(f[medida])))
  return (
    <Tarjeta titulo={titulo}>
      <ul className="flex flex-col gap-2">
        {filas.map((fila) => (
          <li key={etiqueta(fila)} className="grid grid-cols-[6.5rem_1fr_6rem] items-center gap-3 text-sm">
            <span className="text-texto-suave tabular-nums">{etiqueta(fila)}</span>
            <Barra
              etiqueta={etiqueta(fila)}
              valor={Number(fila[medida])}
              maximo={maximo}
              texto={textoMedida(fila[medida], medida)}
            />
            <span className="text-right tabular-nums">
              {medida === 'ventas' ? formatearPrecio(fila.ventas) : fila.pedidos}
            </span>
          </li>
        ))}
      </ul>
    </Tarjeta>
  )
}

// HU-74 · Patrones de demanda: mapa de calor y gráficos por día de la semana y por hora
export default function ReportePatrones({ sedes }) {
  const [filtros, setFiltros] = useState(() => ({ ...rangoPorDefecto(), sede: '' }))
  const [consulta, setConsulta] = useState(filtros)
  const [medida, setMedida] = useState('pedidos')
  const [datos, setDatos] = useState(null)
  const [error, setError] = useState(null)
  const [errorRango, setErrorRango] = useState(null)
  const [consultaCargada, setConsultaCargada] = useState(null)

  useEffect(() => {
    let vigente = true
    obtenerReporteDemanda(consulta)
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
  // Por hora solo las franjas con pedidos, para que el gráfico no tenga 24 filas vacías
  const horasConDemanda = datos ? datos.por_hora.filter((h) => h.pedidos > 0) : []

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
          Prueba con un rango más amplio u otra sede. Solo cuentan los pedidos no cancelados.
        </Alerta>
      )}

      {datos && !datos.sin_datos && (
        <>
          <section aria-label="Resumen" className="grid gap-4 sm:grid-cols-3">
            <Cifra
              titulo="Pedidos"
              valor={datos.totales.pedidos}
              detalle={`${formatearPrecio(datos.totales.ventas)} · ${datos.sede ? datos.sede.nombre : 'Todas las sedes'}`}
            />
            <Cifra
              titulo="Día pico"
              valor={datos.dia_pico.nombre}
              detalle={`${textoMedida(datos.dia_pico.pedidos, 'pedidos')} · ${formatearPrecio(datos.dia_pico.ventas)}`}
            />
            <Cifra
              titulo="Hora pico"
              valor={textoHora(datos.hora_pico.hora)}
              detalle={`${textoMedida(datos.hora_pico.pedidos, 'pedidos')} · ${formatearPrecio(datos.hora_pico.ventas)}`}
            />
          </section>

          <Tarjeta titulo="Mapa de calor por día y hora">
            <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
              <div role="radiogroup" aria-label="Colorear por" className="flex gap-2">
                {MEDIDAS_DEMANDA.map((m) => (
                  <button
                    key={m.valor}
                    type="button"
                    role="radio"
                    aria-checked={medida === m.valor}
                    onClick={() => setMedida(m.valor)}
                    className={`rounded-full px-3 py-1.5 text-sm font-medium ${
                      medida === m.valor ? 'bg-marca text-sobre-marca' : 'bg-superficie-alta text-texto hover:bg-borde'
                    }`}
                  >
                    {m.etiqueta}
                  </button>
                ))}
              </div>
              <BotonExportar tipo="demanda" datos={datos} columnas={COLUMNAS_CSV_CELDAS} filas={datos.celdas} />
            </div>
            <MapaDeCalor datos={datos} medida={medida} />
            <p className="mt-3 text-xs text-texto-suave">
              Cada celda suma todos los días iguales del rango (por ejemplo, todos los viernes) en la hora local en
              que se hizo el pedido. Pasa el cursor sobre una celda para ver su valor y de qué fechas salió.
            </p>
          </Tarjeta>

          <div className="grid gap-4 lg:grid-cols-2 [&>*]:min-w-0">
            <GraficoBarras
              titulo="Por día de la semana"
              filas={datos.por_dia}
              etiqueta={(d) => d.nombre}
              medida={medida}
            />
            <GraficoBarras
              titulo="Por hora (solo horas con pedidos)"
              filas={horasConDemanda}
              etiqueta={(h) => textoHora(h.hora)}
              medida={medida}
            />
          </div>
        </>
      )}
    </div>
  )
}
