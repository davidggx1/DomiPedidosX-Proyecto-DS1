import { useEffect, useState, useCallback } from 'react'
import { useSearchParams } from 'react-router-dom'
import api from '../../api/cliente.js'
import {
  obtenerHorariosSede,
  guardarHorario,
  eliminarHorario,
  obtenerFeriadosSede,
  guardarFeriado,
  eliminarFeriado,
} from '../../api/horarios.js'
import Selector from '../../components/ui/Selector.jsx'
import CampoTexto from '../../components/ui/CampoTexto.jsx'
import Casilla from '../../components/ui/Casilla.jsx'
import Boton from '../../components/ui/Boton.jsx'
import Tarjeta from '../../components/ui/Tarjeta.jsx'
import Alerta from '../../components/ui/Alerta.jsx'

const DIAS = [
  { valor: 'lunes', etiqueta: 'Lunes' },
  { valor: 'martes', etiqueta: 'Martes' },
  { valor: 'miercoles', etiqueta: 'Miércoles' },
  { valor: 'jueves', etiqueta: 'Jueves' },
  { valor: 'viernes', etiqueta: 'Viernes' },
  { valor: 'sabado', etiqueta: 'Sábado' },
  { valor: 'domingo', etiqueta: 'Domingo' },
]

export default function ConfiguracionHorarios() {
  const [searchParams] = useSearchParams()
  const sedeIdUrl = searchParams.get('sede')

  const [sedes, setSedes] = useState([])
  const [sedeSeleccionada, setSedeSeleccionada] = useState(sedeIdUrl || '')
  const [horarios, setHorarios] = useState([])
  const [feriados, setFeriados] = useState([])

  const [mensaje, setMensaje] = useState(null)
  const [error, setError] = useState(null)

  // Formulario Horarios
  const [diaSemana, setDiaSemana] = useState('lunes')
  const [horaApertura, setHoraApertura] = useState('08:00')
  const [horaCierre, setHoraCierre] = useState('20:00')

  // Formulario Feriados
  const [fechaFeriado, setFechaFeriado] = useState('')
  const [descFeriado, setDescFeriado] = useState('')
  const [cerradoFeriado, setCerradoFeriado] = useState(true)

  useEffect(() => {
    let activo = true
    api.get('/sedes/').then(({ data }) => {
      if (activo) {
        const listaSedes = Array.isArray(data) ? data : data.results ?? []
        setSedes(listaSedes)
        if (sedeIdUrl) {
          setSedeSeleccionada(sedeIdUrl)
        }
      }
    })
    return () => { activo = false }
  }, [sedeIdUrl])

  const cargarConfiguracion = useCallback(async () => {
    if (!sedeSeleccionada) return
    try {
      const [h, f] = await Promise.all([
        obtenerHorariosSede(sedeSeleccionada),
        obtenerFeriadosSede(sedeSeleccionada),
      ])
      setHorarios(Array.isArray(h) ? h : h.results ?? [])
      setFeriados(Array.isArray(f) ? f : f.results ?? [])
    } catch {
      setError('Error cargando la configuración de la sede.')
    }
  }, [sedeSeleccionada])

  useEffect(() => {
    let activo = true
    if (sedeSeleccionada) {
      Promise.all([
        obtenerHorariosSede(sedeSeleccionada),
        obtenerFeriadosSede(sedeSeleccionada),
      ]).then(([h, f]) => {
        if (activo) {
          setHorarios(Array.isArray(h) ? h : h.results ?? [])
          setFeriados(Array.isArray(f) ? f : f.results ?? [])
        }
      }).catch(() => {
        if (activo) setError('Error cargando la configuración de la sede.')
      })
    }
    return () => { activo = false }
  }, [sedeSeleccionada])

  const handleGuardarHorario = async (e) => {
    e.preventDefault()
    setError(null)
    setMensaje(null)
    try {
      await guardarHorario({
        sede: sedeSeleccionada,
        dia_semana: diaSemana,
        hora_apertura: horaApertura,
        hora_cierre: horaCierre,
      })
      setMensaje('Horario guardado correctamente.')
      cargarConfiguracion()
    } catch (err) {
      setError(err.response?.data?.non_field_errors?.[0] || 'Error al guardar el horario.')
    }
  }

  const handleGuardarFeriado = async (e) => {
    e.preventDefault()
    setError(null)
    setMensaje(null)
    try {
      await guardarFeriado({
        sede: sedeSeleccionada,
        fecha: fechaFeriado,
        descripcion: descFeriado,
        cerrado: cerradoFeriado,
      })
      setMensaje('Festivo guardado correctamente.')
      setFechaFeriado('')
      setDescFeriado('')
      cargarConfiguracion()
    } catch (err) {
      setError(err.response?.data?.non_field_errors?.[0] || 'Error al guardar el festivo.')
    }
  }

  return (
    <div className="flex flex-col gap-6">
      <header>
        <h1 className="text-2xl font-bold">Horarios de Atención y Festivos</h1>
        <p className="text-texto-suave">Configura las reglas de apertura por sede (HU-82).</p>
      </header>

      {error && <Alerta tipo="error" titulo={error} />}
      {mensaje && <Alerta tipo="exito" titulo={mensaje} />}

      <Tarjeta titulo="Seleccionar Sede">
        <Selector
          etiqueta="Sede"
          opciones={sedes.map((s) => ({ valor: s.id, etiqueta: s.nombre }))}
          value={sedeSeleccionada}
          onChange={(e) => setSedeSeleccionada(e.target.value)}
          textoVacio="-- Selecciona una Sede --"
        />
      </Tarjeta>

      {sedeSeleccionada && (
        <div className="grid gap-6 md:grid-cols-2">
          {/* Horarios Regulares */}
          <Tarjeta titulo="Horarios por Día">
            <form onSubmit={handleGuardarHorario} className="flex flex-col gap-4 mb-6">
              <Selector
                etiqueta="Día de la semana"
                opciones={DIAS}
                value={diaSemana}
                onChange={(e) => setDiaSemana(e.target.value)}
                requerido
              />
              <div className="grid grid-cols-2 gap-3">
                <CampoTexto
                  tipo="time"
                  etiqueta="Apertura"
                  value={horaApertura}
                  onChange={(e) => setHoraApertura(e.target.value)}
                  requerido
                />
                <CampoTexto
                  tipo="time"
                  etiqueta="Cierre"
                  value={horaCierre}
                  onChange={(e) => setHoraCierre(e.target.value)}
                  requerido
                />
              </div>
              <Boton tipo="submit">Guardar Horario</Boton>
            </form>

            <div className="space-y-2">
              {horarios.map((h) => (
                <div key={h.id} className="flex items-center justify-between rounded-lg border border-borde p-3 text-sm">
                  <span className="capitalize font-semibold">{h.dia_semana}</span>
                  <span>{h.hora_apertura} - {h.hora_cierre}</span>
                  <Boton variante="peligro" onClick={async () => { await eliminarHorario(h.id); cargarConfiguracion(); }}>
                    Borrar
                  </Boton>
                </div>
              ))}
            </div>
          </Tarjeta>

          {/* Festivos / Feriados */}
          <Tarjeta titulo="Días Festivos / Especiales">
            <form onSubmit={handleGuardarFeriado} className="flex flex-col gap-4 mb-6">
              <CampoTexto
                tipo="date"
                etiqueta="Fecha"
                value={fechaFeriado}
                onChange={(e) => setFechaFeriado(e.target.value)}
                requerido
              />
              <CampoTexto
                etiqueta="Motivo / Descripción"
                placeholder="Ej. Año Nuevo"
                value={descFeriado}
                onChange={(e) => setDescFeriado(e.target.value)}
                requerido
              />
              <Casilla
                etiqueta="Cierre Total"
                descripcion="Marcar si la sede estará cerrada todo el día"
                checked={cerradoFeriado}
                onChange={(e) => setCerradoFeriado(e.target.checked)}
              />
              <Boton tipo="submit">Agregar Festivo</Boton>
            </form>

            <div className="space-y-2">
              {feriados.map((f) => (
                <div key={f.id} className="flex items-center justify-between rounded-lg border border-borde p-3 text-sm">
                  <div>
                    <p className="font-semibold">{f.fecha} ({f.descripcion})</p>
                    <p className="text-xs text-texto-suave">{f.cerrado ? 'Cerrado todo el día' : `${f.hora_apertura} - ${f.hora_cierre}`}</p>
                  </div>
                  <Boton variante="peligro" onClick={async () => { await eliminarFeriado(f.id); cargarConfiguracion(); }}>
                    Borrar
                  </Boton>
                </div>
              ))}
            </div>
          </Tarjeta>
        </div>
      )}
    </div>
  )
}