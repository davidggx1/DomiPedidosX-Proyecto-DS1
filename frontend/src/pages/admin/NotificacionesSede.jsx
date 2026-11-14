import { useEffect, useState } from 'react'
import api from '../../api/cliente.js'
import { interpretarError } from '../../api/errores.js'
import { crearSuscripcion, eliminarSuscripcion, obtenerSuscripciones } from '../../api/notificacionesSede.js'
import Alerta from '../../components/ui/Alerta.jsx'
import Boton from '../../components/ui/Boton.jsx'
import CampoTexto from '../../components/ui/CampoTexto.jsx'
import Casilla from '../../components/ui/Casilla.jsx'
import Selector from '../../components/ui/Selector.jsx'
import Tarjeta from '../../components/ui/Tarjeta.jsx'
import {
  EVENTOS_SEDE,
  ROLES_SUSCRIBIBLES,
  agruparPorEvento,
  resumenDestinatarios,
  validarCorreoNuevo,
} from '../../utils/notificacionesSede.js'

// Un evento: casillas por rol y lista de correos sueltos.
function TarjetaEvento({ evento, grupo, ocupado, alCambiarRol, alAgregarCorreo, alQuitarCorreo }) {
  const [correo, setCorreo] = useState('')
  const [error, setError] = useState(null)

  async function agregar(e) {
    e.preventDefault()
    const problema = validarCorreoNuevo(correo, grupo.correos)
    if (problema) {
      setError(problema)
      return
    }
    const guardado = await alAgregarCorreo(correo.trim().toLowerCase())
    if (guardado) {
      setCorreo('')
      setError(null)
    }
  }

  return (
    <Tarjeta titulo={evento.titulo}>
      <p className="text-sm text-texto-suave">{evento.descripcion}</p>
      <p className="mt-1 text-sm font-medium" aria-live="polite">
        {resumenDestinatarios(grupo)}
      </p>

      <fieldset className="mt-4">
        <legend className="text-sm font-semibold">Roles de la sede</legend>
        <div className="mt-2 grid grid-cols-[repeat(auto-fill,minmax(11rem,1fr))] gap-x-4 gap-y-2">
          {ROLES_SUSCRIBIBLES.map((rol) => (
            <Casilla
              key={rol.valor}
              etiqueta={rol.etiqueta}
              checked={Boolean(grupo.roles[rol.valor])}
              disabled={ocupado}
              onChange={(e) => alCambiarRol(rol.valor, e.target.checked)}
            />
          ))}
        </div>
        <p className="mt-2 text-xs text-texto-suave">
          Le llega a todo el personal activo con ese rol en esta sede. Los administradores son de todas las sedes.
        </p>
      </fieldset>

      <div className="mt-4">
        <h3 className="text-sm font-semibold">Otros correos</h3>
        {grupo.correos.length > 0 && (
          <ul className="mt-2 flex flex-wrap gap-2">
            {grupo.correos.map((suscripcion) => (
              <li
                key={suscripcion.id}
                className="flex items-center gap-1 rounded-full border border-borde bg-superficie-alta py-1 pr-1 pl-3 text-sm"
              >
                <span className="break-all">{suscripcion.correo}</span>
                <button
                  type="button"
                  disabled={ocupado}
                  onClick={() => alQuitarCorreo(suscripcion)}
                  aria-label={`Quitar ${suscripcion.correo}`}
                  className="inline-flex size-8 items-center justify-center rounded-full text-texto-suave hover:bg-borde hover:text-texto disabled:opacity-50"
                >
                  ✕
                </button>
              </li>
            ))}
          </ul>
        )}
        <form onSubmit={agregar} className="mt-2 flex flex-wrap items-start gap-2" noValidate>
          <CampoTexto
            etiqueta={`Agregar correo a "${evento.titulo}"`}
            className="min-w-0 flex-1 basis-56 [&>label]:sr-only"
            type="email"
            placeholder="gerente@empresa.com"
            value={correo}
            error={error}
            onChange={(e) => {
              setCorreo(e.target.value)
              setError(null)
            }}
          />
          <Boton tipo="submit" variante="secundario" disabled={ocupado}>
            Agregar
          </Boton>
        </form>
      </div>
    </Tarjeta>
  )
}

// HU-83 · El administrador elige quién recibe por correo los avisos de cada sede.
export default function NotificacionesSede() {
  const [sedes, setSedes] = useState([])
  const [sede, setSede] = useState('')
  const [suscripciones, setSuscripciones] = useState([])
  // Sede cuyas suscripciones ya están en pantalla; mientras no sea la elegida, se está cargando
  const [sedeCargada, setSedeCargada] = useState(null)
  const [ocupado, setOcupado] = useState(false)
  const [error, setError] = useState(null)
  const [mensaje, setMensaje] = useState(null)

  useEffect(() => {
    api
      .get('/sedes/')
      .then(({ data }) => {
        const lista = Array.isArray(data) ? data : (data.results ?? [])
        setSedes(lista)
        if (lista.length) setSede((actual) => actual || String(lista[0].id))
      })
      .catch((fallo) => setError(interpretarError(fallo).general))
  }, [])

  useEffect(() => {
    if (!sede) return
    let vigente = true
    obtenerSuscripciones(sede)
      .then((datos) => {
        if (!vigente) return
        setSuscripciones(datos)
        setError(null)
      })
      .catch((fallo) => vigente && setError(interpretarError(fallo).general))
      .finally(() => vigente && setSedeCargada(sede))
    return () => {
      vigente = false
    }
  }, [sede])

  // Ejecuta un cambio, muestra el resultado y devuelve si salió bien
  async function cambiar(accion, textoExito) {
    setOcupado(true)
    setMensaje(null)
    try {
      await accion()
      setError(null)
      setMensaje(textoExito)
      return true
    } catch (fallo) {
      const { general, campos } = interpretarError(fallo)
      setError(general ?? Object.values(campos)[0] ?? 'No se pudo guardar el cambio.')
      return false
    } finally {
      setOcupado(false)
    }
  }

  const cargando = sedeCargada !== sede
  const grupos = agruparPorEvento(suscripciones)
  const nombreSede = sedes.find((s) => String(s.id) === sede)?.nombre ?? ''

  function cambiarRol(evento, rol, activo) {
    const etiqueta = ROLES_SUSCRIBIBLES.find((r) => r.valor === rol).etiqueta
    const titulo = EVENTOS_SEDE.find((e) => e.valor === evento).titulo
    if (activo) {
      return cambiar(async () => {
        const nueva = await crearSuscripcion({ sede: Number(sede), evento, rol })
        setSuscripciones((lista) => [...lista, nueva])
      }, `${etiqueta} recibirá "${titulo}".`)
    }
    const actual = grupos[evento].roles[rol]
    return cambiar(async () => {
      await eliminarSuscripcion(actual.id)
      setSuscripciones((lista) => lista.filter((s) => s.id !== actual.id))
    }, `${etiqueta} ya no recibirá "${titulo}".`)
  }

  function agregarCorreo(evento, correo) {
    return cambiar(async () => {
      const nueva = await crearSuscripcion({ sede: Number(sede), evento, correo })
      setSuscripciones((lista) => [...lista, nueva])
    }, `${correo} recibirá este aviso.`)
  }

  function quitarCorreo(suscripcion) {
    return cambiar(async () => {
      await eliminarSuscripcion(suscripcion.id)
      setSuscripciones((lista) => lista.filter((s) => s.id !== suscripcion.id))
    }, `${suscripcion.correo} ya no recibirá este aviso.`)
  }

  return (
    <div className="flex flex-col gap-6">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold">Notificaciones de la sede</h1>
          <p className="text-texto-suave">
            Elige quién recibe por correo los avisos de cada sede. Los avisos en pantalla del operador no cambian.
          </p>
        </div>
        <Selector
          etiqueta="Sede"
          name="sede"
          value={sede}
          onChange={(e) => {
            setSede(e.target.value)
            setMensaje(null)
          }}
          opciones={sedes.map((s) => ({ valor: String(s.id), etiqueta: s.nombre }))}
          textoVacio="Selecciona una sede"
        />
      </header>

      {error && <Alerta tipo="error">{error}</Alerta>}
      {mensaje && <Alerta tipo="exito">{mensaje}</Alerta>}

      {!sede ? (
        <p className="text-texto-suave">{sedes.length ? 'Selecciona una sede.' : 'Aún no hay sedes registradas.'}</p>
      ) : cargando ? (
        <p className="text-texto-suave">Cargando las notificaciones de {nombreSede}…</p>
      ) : (
        <div className="grid gap-4 lg:grid-cols-3">
          {EVENTOS_SEDE.map((evento) => (
            <TarjetaEvento
              key={`${sede}-${evento.valor}`}
              evento={evento}
              grupo={grupos[evento.valor]}
              ocupado={ocupado}
              alCambiarRol={(rol, activo) => cambiarRol(evento.valor, rol, activo)}
              alAgregarCorreo={(correo) => agregarCorreo(evento.valor, correo)}
              alQuitarCorreo={quitarCorreo}
            />
          ))}
        </div>
      )}
    </div>
  )
}
