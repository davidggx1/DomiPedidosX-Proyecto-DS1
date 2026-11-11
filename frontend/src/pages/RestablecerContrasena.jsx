import { useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { restablecerContrasena } from '../api/contrasena.js'
import { interpretarError } from '../api/errores.js'
import Alerta from '../components/ui/Alerta.jsx'
import Boton from '../components/ui/Boton.jsx'
import CampoTexto from '../components/ui/CampoTexto.jsx'
import Tarjeta from '../components/ui/Tarjeta.jsx'

const MINIMO = 8

const PEDIR_OTRO = (
  <Link to="/recuperar-contrasena" className="text-marca-clara underline underline-offset-4">
    Solicitar un enlace nuevo
  </Link>
)

// HU-05 · Paso 2: se llega desde el enlace del correo (?uid=…&token=…)
// y se elige la nueva contraseña. El enlace vence en 1 hora y sirve una sola vez.
export default function RestablecerContrasena() {
  const [parametros] = useSearchParams()
  const uid = parametros.get('uid')
  const token = parametros.get('token')
  const [datos, setDatos] = useState({ password: '', confirmacion: '' })
  const [errores, setErrores] = useState({})
  const [listo, setListo] = useState(null)
  const [guardando, setGuardando] = useState(false)

  function cambiar(evento) {
    const { name, value } = evento.target
    setDatos((actuales) => ({ ...actuales, [name]: value }))
  }

  function validar() {
    const encontrados = {}
    if (datos.password.length < MINIMO) encontrados.password = `Debe tener al menos ${MINIMO} caracteres.`
    if (datos.confirmacion !== datos.password) encontrados.confirmacion = 'Las contraseñas no coinciden.'
    return encontrados
  }

  async function guardar(evento) {
    evento.preventDefault()
    const encontrados = validar()
    setErrores(encontrados)
    if (Object.keys(encontrados).length > 0) return

    setGuardando(true)
    try {
      const { detail } = await restablecerContrasena({ uid, token, password: datos.password })
      setListo(detail)
    } catch (fallo) {
      const { general, campos } = interpretarError(fallo)
      setErrores({ general, ...campos })
    } finally {
      setGuardando(false)
    }
  }

  let contenido
  if (!uid || !token) {
    contenido = (
      <Alerta tipo="error" titulo="El enlace está incompleto">
        <p>Abre el enlace tal como llegó a tu correo, o {PEDIR_OTRO}.</p>
      </Alerta>
    )
  } else if (listo) {
    contenido = (
      <div className="flex flex-col gap-3">
        <Alerta tipo="exito" titulo={listo} />
        <Link
          to="/login"
          className="inline-flex min-h-11 items-center justify-center rounded-lg bg-marca px-4 py-2 font-medium text-white hover:bg-marca-oscura"
        >
          Iniciar sesión
        </Link>
      </div>
    )
  } else {
    contenido = (
      <form noValidate onSubmit={guardar} className="flex flex-col gap-3">
        {errores.general && (
          <Alerta tipo="error" titulo={errores.general}>
            {!errores.password && <p>{PEDIR_OTRO}</p>}
          </Alerta>
        )}
        <CampoTexto
          etiqueta="Nueva contraseña"
          name="password"
          type="password"
          autoComplete="new-password"
          requerido
          ayuda={`Mínimo ${MINIMO} caracteres. Evita contraseñas comunes o solo números.`}
          value={datos.password}
          error={errores.password}
          onChange={cambiar}
        />
        <CampoTexto
          etiqueta="Confirma la nueva contraseña"
          name="confirmacion"
          type="password"
          autoComplete="new-password"
          requerido
          value={datos.confirmacion}
          error={errores.confirmacion}
          onChange={cambiar}
        />
        <Boton tipo="submit" cargando={guardando}>
          Guardar contraseña
        </Boton>
      </form>
    )
  }

  return (
    <div className="mx-auto flex max-w-md flex-col gap-4">
      <h1 className="text-2xl font-bold">Nueva contraseña</h1>
      <Tarjeta>{contenido}</Tarjeta>
    </div>
  )
}
