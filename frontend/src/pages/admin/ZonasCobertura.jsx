import { useCallback, useEffect, useMemo, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import api from '../../api/cliente.js'
import { interpretarError } from '../../api/errores.js'
import { actualizarZona, crearZona, eliminarZona, listarZonas } from '../../api/zonas.js'
import FormularioZona from '../../components/zonas/FormularioZona.jsx'
import MapaZonas from '../../components/zonas/MapaZonas.jsx'
import Alerta from '../../components/ui/Alerta.jsx'
import Boton from '../../components/ui/Boton.jsx'
import Modal from '../../components/ui/Modal.jsx'
import Selector from '../../components/ui/Selector.jsx'
import Tarjeta from '../../components/ui/Tarjeta.jsx'
import Interruptor from '../../components/ui/Interruptor.jsx'
import {
  formatearTarifa,
  formatearTiempo,
  validarTarifaTiempo,
  zonaConfigurada,
} from '../../utils/zonas.js'


const VACIO = {
  nombre: '',
  tarifa_domicilio: '',
  tiempo_estimado: '',
  pedido_minimo: '',
  activo: true,
}

// Forma de una zona existente, en el formato que entiende el mapa.
function formaDeZona(zona) {
  return zona.tipo === 'poligono'
    ? { tipo: 'poligono', poligono_vertices: zona.poligono_vertices }
    : {
        tipo: 'radio',
        centro_latitud: zona.centro_latitud,
        centro_longitud: zona.centro_longitud,
        radio: zona.radio,
      }
}

function describirForma(forma) {
  if (!forma) return null
  return forma.tipo === 'radio'
    ? `Círculo de ${forma.radio.toFixed(2)} km de radio`
    : `Polígono de ${forma.poligono_vertices.length} puntos`
}

export default function ZonasCobertura() {
  const [parametros, setParametros] = useSearchParams()
  const sedeId = parametros.get('sede') ?? ''

  const [sedes, setSedes] = useState([])
  const [zonas, setZonas] = useState([])
  const [cargando, setCargando] = useState(false)
  const [error, setError] = useState(null)
  const [exito, setExito] = useState(null)

  // Edición: null = nada abierto; { zona: null } = nueva; { zona } = editando.
  const [edicion, setEdicion] = useState(null)
  const [valores, setValores] = useState(VACIO)
  const [forma, setForma] = useState(null)
  const [errores, setErrores] = useState({})
  const [errorGeneral, setErrorGeneral] = useState(null)
  const [guardando, setGuardando] = useState(false)
  const [zonaConPedidos, setZonaConPedidos] = useState(null)

  useEffect(() => {
    let activo = true
    api
      .get('/sedes/')
      .then(({ data }) => {
        if (activo) setSedes(Array.isArray(data) ? data : (data.results ?? []))
      })
      .catch(() => activo && setError('No fue posible cargar las sedes.'))
    return () => {
      activo = false
    }
  }, [])

  const recargar = useCallback(async () => {
    if (!sedeId) {
      setZonas([])
      return
    }
    setCargando(true)
    try {
      setZonas(await listarZonas(sedeId))
      setError(null)
    } catch (e) {
      setError(interpretarError(e).general)
    } finally {
      setCargando(false)
    }
  }, [sedeId])

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    recargar()
  }, [recargar])

  const sede = sedes.find((s) => String(s.id) === sedeId)
  const centroSede = sede ? [sede.latitud, sede.longitud] : undefined

  const abrirNueva = () => {
    setEdicion({ zona: null })
    setValores(VACIO)
    setForma(null)
    setErrores({})
    setErrorGeneral(null)
    setExito(null)
  }

  const abrirEditar = (zona) => {
    setEdicion({ zona })
    setValores({
      nombre: zona.nombre,
      tarifa_domicilio: zona.tarifa_domicilio ?? '',
      tiempo_estimado: zona.tiempo_estimado ?? '',
      pedido_minimo: zona.pedido_minimo,
      activo: zona.activo,
    })
    setForma(formaDeZona(zona))
    setErrores({})
    setErrorGeneral(null)
    setExito(null)
  }

  const cerrar = useCallback(() => setEdicion(null), [])

  const guardar = async (evento) => {
    evento.preventDefault()
    setErrores({})
    setErrorGeneral(null)
    if (!forma) {
      setErrorGeneral('Dibuja la zona en el mapa antes de guardar.')
      return
    }
    if (forma.tipo === 'radio' && !(forma.radio > 0)) {
      setErrores({ radio: 'El radio debe ser mayor que 0 km.' })
      return
    }

    const erroresTarifa = validarTarifaTiempo(valores)
    if (Object.keys(erroresTarifa).length > 0) {
      setErrores(erroresTarifa)
      return
    }

    const datos = {
      sede: Number(sedeId),
      nombre: valores.nombre,
      tarifa_domicilio: valores.tarifa_domicilio === '' ? null : valores.tarifa_domicilio,
      tiempo_estimado: valores.tiempo_estimado === '' ? null : Number(valores.tiempo_estimado),
      pedido_minimo: valores.pedido_minimo,
      activo: valores.activo,
      ...(forma.tipo === 'radio'
        ? {
            poligono_vertices: null,
            radio: forma.radio,
            centro_latitud: forma.centro_latitud,
            centro_longitud: forma.centro_longitud,
          }
        : { poligono_vertices: forma.poligono_vertices }),
    }

    setGuardando(true)
    try {
        const guardada = edicion.zona
        ? await actualizarZona(edicion.zona.id, datos)
        : await crearZona(datos)
      setExito(
        guardada.activo
          ? `Zona "${valores.nombre}" guardada. Aplica a los pedidos futuros.`
          : `Zona "${valores.nombre}" guardada como desactivada.`,
      )
      setEdicion(null)
      recargar()
    } catch (e) {
      const { general, campos } = interpretarError(e)
      setErrores(campos)
      setErrorGeneral(general)
    } finally {
      setGuardando(false)
    }
  }

  const eliminar = async (zona) => {
    setError(null)
    setExito(null)
    try {
      await eliminarZona(zona.id)
      setExito(`Zona "${zona.nombre}" eliminada.`)
      recargar()
    } catch (e) {
      if (e.response?.status === 409) setZonaConPedidos(zona)
      else setError(interpretarError(e).general)
    }
  }

  const desactivar = async (zona) => {
    setZonaConPedidos(null)
    try {
      await actualizarZona(zona.id, { activo: false })
      setExito(`Zona "${zona.nombre}" desactivada.`)
      recargar()
    } catch (e) {
      setError(interpretarError(e).general)
    }
  }

  const alternarActiva = async (zona) => {
    setError(null)
    setExito(null)
    try {
      await actualizarZona(zona.id, { activo: !zona.activo })
      setExito(
        `Zona "${zona.nombre}" ${zona.activo ? 'desactivada' : 'activada'}. Aplica a los pedidos futuros.`,
      )
      recargar()
    } catch (e) {
      const { general, campos } = interpretarError(e)
      setError(campos.activo ?? general)
    }
  }


  const otras = useMemo(
    () => zonas.filter((z) => z.id !== edicion?.zona?.id),
    [zonas, edicion],
  )

  return (
    <div className="flex flex-col gap-6">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold">Zonas de cobertura</h1>
          <p className="text-texto-suave">
            Delimita dónde opera el domicilio de cada sede. Los cambios aplican a pedidos futuros.
          </p>
        </div>
        <Selector
          etiqueta="Sede"
          textoVacio="Selecciona una sede"
          opciones={sedes.map((s) => ({ valor: s.id, etiqueta: s.nombre }))}
          value={sedeId}
          onChange={(e) => {
            setParametros(e.target.value ? { sede: e.target.value } : {})
            setEdicion(null)
          }}
          className="min-w-56"
        />
      </header>

      {error && <Alerta tipo="error" titulo={error} />}
      {exito && <Alerta tipo="exito" titulo={exito} />}

      {!sedeId ? (
        <Tarjeta>
          <p className="text-texto-suave">Selecciona una sede para ver y editar sus zonas.</p>
        </Tarjeta>
      ) : edicion ? (
        <div className="grid gap-4 lg:grid-cols-2">
          <div className="flex flex-col gap-3">
            <h2 className="text-lg font-bold">
              {edicion.zona ? `Editar "${edicion.zona.nombre}"` : 'Nueva zona'}
            </h2>
            {errorGeneral && <Alerta tipo="error" titulo={errorGeneral} />}
            <Tarjeta>
              <FormularioZona
                valores={valores}
                alCambiar={setValores}
                errores={errores}
                resumenForma={describirForma(forma)}
                guardando={guardando}
                alGuardar={guardar}
                alCancelar={cerrar}
              />
            </Tarjeta>
          </div>
          <MapaZonas
            key={edicion.zona?.id ?? 'nueva'}
            formaInicial={edicion.zona ? formaDeZona(edicion.zona) : null}
            otras={otras}
            centro={centroSede}
            alCambiar={setForma}
          />
        </div>
      ) : (
        <div className="grid gap-4 lg:grid-cols-2">
          <div className="flex flex-col gap-3">
            <div className="flex items-center justify-between">
              <h2 className="text-lg font-bold">Zonas de {sede?.nombre}</h2>
              <Boton onClick={abrirNueva}>+ Nueva zona</Boton>
            </div>
            {cargando ? (
              <p className="text-texto-suave">Cargando zonas…</p>
            ) : zonas.length === 0 ? (
              <Tarjeta>
                <p className="text-texto-suave">Esta sede aún no tiene zonas de cobertura.</p>
              </Tarjeta>
            ) : (
              zonas.map((zona) => (
                <Tarjeta key={zona.id} className="flex flex-col gap-3">
                  <div className="flex items-center justify-between gap-2">
                    <h3 className="font-bold">{zona.nombre}</h3>
                    <div className="flex items-center gap-2">
                      <span
                        className={`rounded-full border px-2.5 py-0.5 text-xs font-medium ${
                          zona.activo ? 'border-exito text-exito' : 'border-borde text-texto-suave'
                        }`}
                      >
                        {zona.activo ? 'Activa' : 'Desactivada'}
                      </span>
                      <Interruptor
                        activo={zona.activo}
                        alCambiar={() => alternarActiva(zona)}
                        etiqueta={`${zona.activo ? 'Desactivar' : 'Activar'} zona ${zona.nombre}`}
                        disabled={!zona.activo && !zonaConfigurada(zona)}
                      />
                    </div>
                  </div>
                  <p className="text-sm text-texto-suave">
                    {zona.tipo === 'poligono'
                      ? `Polígono (${zona.poligono_vertices.length} puntos)`
                      : `Radio de ${zona.radio.toFixed(2)} km`}
                    {' · '}
                    {formatearTarifa(zona.tarifa_domicilio)} de domicilio
                    {' · '}
                    {formatearTiempo(zona.tiempo_estimado)}
                    {' · '}mínimo ${Number(zona.pedido_minimo).toLocaleString('es-CO')}
                  </p>
                  {!zonaConfigurada(zona) && (
                    <p className="text-sm text-aviso">Define tarifa y tiempo para poder activarla.</p>
                  )}
                  <div className="flex gap-2">
                    <Boton variante="fantasma" className="flex-1 text-sm" onClick={() => abrirEditar(zona)}>
                      Editar
                    </Boton>
                    <Boton variante="peligro" className="flex-1 text-sm" onClick={() => eliminar(zona)}>
                      Eliminar
                    </Boton>
                  </div>
                </Tarjeta>
              ))
            )}
          </div>
          <MapaZonas key={`ver-${sedeId}-${zonas.length}`} otras={zonas} centro={centroSede} alCambiar={() => {}} />
        </div>
      )}

      {zonaConPedidos && (
        <Modal
          titulo="Esta zona tiene pedidos"
          alCerrar={() => setZonaConPedidos(null)}
          acciones={
            <>
              <Boton variante="secundario" onClick={() => setZonaConPedidos(null)}>
                Cancelar
              </Boton>
              <Boton onClick={() => desactivar(zonaConPedidos)}>Desactivar zona</Boton>
            </>
          }
        >
          <p className="text-sm">
            «{zonaConPedidos.nombre}» tiene pedidos asociados y no se puede eliminar. Puedes
            desactivarla: dejará de recibir pedidos nuevos y el historial no cambia.
          </p>
        </Modal>
      )}
    </div>
  )
}