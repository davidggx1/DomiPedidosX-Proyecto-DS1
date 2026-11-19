import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { interpretarError } from '../../api/errores.js'
import { listarSedesMenu } from '../../api/menu.js'
import { actualizarEmpleado, obtenerEmpleado } from '../../api/usuarios.js'
import Alerta from '../../components/ui/Alerta.jsx'
import Boton from '../../components/ui/Boton.jsx'
import CampoTexto from '../../components/ui/CampoTexto.jsx'
import Selector from '../../components/ui/Selector.jsx'
import Tarjeta from '../../components/ui/Tarjeta.jsx'
import {
  ROLES_PERSONAL,
  TIPOS_DOCUMENTO,
  armarCuerpoEmpleado,
  cambiosDeAcceso,
  claseEstadoCuenta,
  datosInicialesEmpleado,
  requiereSede,
  soloDigitos,
  validarEmpleado,
} from '../../utils/personal.js'

// HU-80 · El administrador edita los datos, el rol y la sede de una cuenta del personal
// (activa o inactiva) y puede reactivarla.
export default function EditarEmpleado() {
  const { id } = useParams()
  const [empleado, setEmpleado] = useState(null)
  const [datos, setDatos] = useState(null)
  const [sedes, setSedes] = useState([])
  const [errores, setErrores] = useState({})
  const [errorCarga, setErrorCarga] = useState(null)
  const [mensaje, setMensaje] = useState(null)
  const [guardando, setGuardando] = useState(false)
  const [cambiandoEstado, setCambiandoEstado] = useState(false)

  useEffect(() => {
    let vigente = true
    Promise.all([obtenerEmpleado(id), listarSedesMenu().catch(() => [])])
      .then(([detalle, listaSedes]) => {
        if (!vigente) return
        setEmpleado(detalle)
        setDatos(datosInicialesEmpleado(detalle))
        setSedes(Array.isArray(listaSedes) ? listaSedes : (listaSedes?.sedes ?? []))
      })
      .catch((error) => {
        if (vigente) setErrorCarga(interpretarError(error).general)
      })
    return () => {
      vigente = false
    }
  }, [id])

  function cambiar(evento) {
    const { name, value } = evento.target
    const nuevo = name === 'celular' ? soloDigitos(value) : value
    setDatos((actuales) => ({ ...actuales, [name]: nuevo }))
    setErrores((actuales) => {
      if (!actuales[name]) return actuales
      const resto = { ...actuales }
      delete resto[name]
      return resto
    })
  }

  function aplicar(actualizado) {
    setEmpleado(actualizado)
    setDatos(datosInicialesEmpleado(actualizado))
  }

  async function guardar(evento) {
    evento.preventDefault()
    setMensaje(null)

    const erroresLocales = validarEmpleado(datos)
    setErrores(erroresLocales)
    if (Object.keys(erroresLocales).length > 0) {
      setMensaje({ tipo: 'error', texto: 'Revisa los campos marcados.' })
      return
    }

    const cambios = cambiosDeAcceso(empleado, datos, sedes)
    if (
      cambios.length > 0 &&
      !window.confirm(
        `Vas a cambiar el acceso de ${empleado.nombres}:\n- ${cambios.join('\n- ')}\n\n` +
          'Los permisos nuevos valen desde ya; verá el menú nuevo al iniciar sesión otra vez. ¿Continuar?',
      )
    ) {
      return
    }

    setGuardando(true)
    try {
      aplicar(await actualizarEmpleado(id, armarCuerpoEmpleado(datos)))
      setMensaje({ tipo: 'exito', texto: 'Se guardaron los cambios.' })
    } catch (error) {
      const { general, campos } = interpretarError(error)
      setErrores(campos)
      setMensaje({ tipo: 'error', texto: campos.rol ?? campos.sede_id ?? general })
    } finally {
      setGuardando(false)
    }
  }

  async function cambiarEstado() {
    const desactivar = empleado.activa
    const pregunta = desactivar
      ? `¿Desactivar la cuenta de ${empleado.nombres}? No podrá iniciar sesión.`
      : `¿Reactivar la cuenta de ${empleado.nombres}? Podrá volver a iniciar sesión.`
    if (!window.confirm(pregunta)) return
    setCambiandoEstado(true)
    setMensaje(null)
    try {
      const actualizado = await actualizarEmpleado(id, { activa: !desactivar })
      setEmpleado(actualizado)
      setMensaje({
        tipo: 'exito',
        texto: desactivar ? 'Se desactivó la cuenta.' : 'Se reactivó la cuenta: ya puede iniciar sesión.',
      })
    } catch (error) {
      const { general, campos } = interpretarError(error)
      setMensaje({ tipo: 'error', texto: campos.activa ?? general })
    } finally {
      setCambiandoEstado(false)
    }
  }

  if (errorCarga) {
    return (
      <div className="flex flex-col gap-4">
        <Alerta tipo="error" titulo={errorCarga} />
        <Link to="/admin/personal" className="text-marca-clara underline underline-offset-4">
          Volver al personal
        </Link>
      </div>
    )
  }
  if (!empleado || !datos) return <p className="text-texto-suave">Cargando cuenta…</p>

  // Si la sede actual ya no está activa, igual se muestra para no perder el valor.
  const opcionesSede = sedes.map((sede) => ({ valor: String(sede.id), etiqueta: sede.nombre }))
  if (datos.sede_id && !opcionesSede.some((opcion) => opcion.valor === datos.sede_id)) {
    opcionesSede.push({ valor: datos.sede_id, etiqueta: empleado.sede ?? `Sede ${datos.sede_id}` })
  }

  return (
    <div className="mx-auto flex max-w-2xl flex-col gap-4">
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold">Editar cuenta del personal</h1>
          <p className="text-texto-suave">{empleado.email}</p>
        </div>
        <Link to="/admin/personal" className="text-marca-clara underline underline-offset-4">
          Volver al personal
        </Link>
      </header>

      {mensaje && <Alerta tipo={mensaje.tipo} titulo={mensaje.texto} />}

      <Tarjeta titulo="Estado de la cuenta">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <span
            className={`rounded-full border px-2 py-0.5 text-xs font-medium ${claseEstadoCuenta(empleado.activa)}`}
          >
            {empleado.activa ? 'Activa' : 'Desactivada'}
          </span>
          <Boton
            variante={empleado.activa ? 'peligro' : 'primario'}
            cargando={cambiandoEstado}
            onClick={cambiarEstado}
          >
            {empleado.activa ? 'Desactivar cuenta' : 'Reactivar cuenta'}
          </Boton>
        </div>
        {!empleado.activa && (
          <p className="mt-2 text-sm text-texto-suave">
            Mientras esté desactivada no puede iniciar sesión. Puedes editar sus datos y reactivarla cuando quieras.
          </p>
        )}
      </Tarjeta>

      <Tarjeta titulo="Datos">
        <form noValidate onSubmit={guardar} className="flex flex-col gap-3">
          <div className="grid gap-3 sm:grid-cols-2">
            <CampoTexto etiqueta="Nombres" name="nombres" requerido value={datos.nombres}
              onChange={cambiar} error={errores.nombres} />
            <CampoTexto etiqueta="Apellidos" name="apellidos" requerido value={datos.apellidos}
              onChange={cambiar} error={errores.apellidos} />
          </div>
          <div className="grid gap-3 sm:grid-cols-2">
            <Selector etiqueta="Tipo de documento" name="tipo_documento" opciones={TIPOS_DOCUMENTO}
              value={datos.tipo_documento} onChange={cambiar} error={errores.tipo_documento} />
            <CampoTexto etiqueta="Número de documento" name="num_documento" maxLength={12} requerido
              value={datos.num_documento} onChange={cambiar} error={errores.num_documento} />
          </div>
          <CampoTexto etiqueta="Celular" name="celular" type="tel" inputMode="numeric" maxLength={10}
            requerido ayuda="10 dígitos, sin espacios." value={datos.celular} onChange={cambiar}
            error={errores.celular} />
          <CampoTexto etiqueta="Dirección" name="direccion" requerido value={datos.direccion}
            onChange={cambiar} error={errores.direccion} />

          <div className="grid gap-3 sm:grid-cols-2">
            <Selector etiqueta="Rol" name="rol" opciones={ROLES_PERSONAL} requerido value={datos.rol}
              onChange={cambiar} error={errores.rol} />
            {requiereSede(datos.rol) && (
              <Selector etiqueta="Sede" name="sede_id" opciones={opcionesSede} requerido
                textoVacio="Elige una sede…" value={datos.sede_id} onChange={cambiar}
                error={errores.sede_id} />
            )}
          </div>
          <p className="text-sm text-texto-suave">
            El correo no se puede cambiar. Si cambias el rol o la sede, los permisos nuevos valen desde ya y la
            persona ve su menú nuevo al volver a iniciar sesión.
          </p>

          <div>
            <Boton tipo="submit" cargando={guardando}>
              Guardar cambios
            </Boton>
          </div>
        </form>
      </Tarjeta>
    </div>
  )
}