import { useState } from 'react'
import { Link, Navigate } from 'react-router-dom'
import { registrarCliente } from '../api/usuarios.js'
import { interpretarError } from '../api/errores.js'
import { useAuth } from '../auth/useAuth.js'
import { rutaInicio } from '../auth/roles.js'
import Alerta from '../components/ui/Alerta.jsx'
import Boton from '../components/ui/Boton.jsx'
import CampoTexto from '../components/ui/CampoTexto.jsx'
import Selector from '../components/ui/Selector.jsx'
import Tarjeta from '../components/ui/Tarjeta.jsx'
import {
  OPCIONES_TIPO_DOCUMENTO,
  armarCuerpoRegistro,
  fechaHoy,
  soloDigitos,
  validarRegistro,
} from '../utils/registro.js'

const DATOS_INICIALES = {
  email: '',
  password: '',
  confirmarPassword: '',
  tipo_documento: '',
  num_documento: '',
  nombres: '',
  apellidos: '',
  celular: '',
  fecha_nacimiento: '',
}

// HU-01 y HU-02: el cliente crea su cuenta con sus datos personales y un celular de 10 dígitos.
// El backend no devuelve sesión, así que al terminar se invita a iniciar sesión.
export default function Registro() {
  const { usuario } = useAuth()
  const [datos, setDatos] = useState(DATOS_INICIALES)
  const [errores, setErrores] = useState({})
  const [errorGeneral, setErrorGeneral] = useState(null)
  const [enviando, setEnviando] = useState(false)
  const [correoRegistrado, setCorreoRegistrado] = useState(null)

  if (usuario) {
    return <Navigate to={rutaInicio(usuario.rol)} replace />
  }

  function cambiar(evento) {
    const { name, value } = evento.target
    const nuevo = name === 'celular' ? soloDigitos(value) : value
    setDatos((actuales) => ({ ...actuales, [name]: nuevo }))
    // Al corregir un campo, se quita su error.
    setErrores((actuales) => {
      if (!actuales[name]) return actuales
      const resto = { ...actuales }
      delete resto[name]
      return resto
    })
  }

  async function enviar(evento) {
    evento.preventDefault()
    setErrorGeneral(null)

    const erroresLocales = validarRegistro(datos)
    setErrores(erroresLocales)
    if (Object.keys(erroresLocales).length > 0) {
      setErrorGeneral('Revisa los campos marcados.')
      return
    }

    setEnviando(true)
    try {
      const respuesta = await registrarCliente(armarCuerpoRegistro(datos))
      setCorreoRegistrado(respuesta.email ?? datos.email)
    } catch (error) {
      const { general, campos } = interpretarError(error)
      setErrores(campos)
      setErrorGeneral(general)
    } finally {
      setEnviando(false)
    }
  }

  if (correoRegistrado) {
    return (
      <div className="mx-auto flex max-w-md flex-col gap-4">
        <h1 className="text-2xl font-bold">Cuenta creada</h1>
        <Alerta tipo="info" titulo="Cuenta creada correctamente.">
          Ya puedes iniciar sesión con {correoRegistrado}.
        </Alerta>
        <Link to="/login" className="self-start text-marca-clara underline underline-offset-4">
          Ir a iniciar sesión
        </Link>
      </div>
    )
  }

  return (
    <div className="mx-auto flex max-w-md flex-col gap-4">
      <h1 className="text-2xl font-bold">Crear cuenta</h1>

      <Tarjeta titulo="Tus datos">
        <form noValidate onSubmit={enviar} className="flex flex-col gap-3">
          {errorGeneral && <Alerta tipo="error" titulo={errorGeneral} />}

          <CampoTexto
            etiqueta="Nombres"
            name="nombres"
            autoComplete="given-name"
            requerido
            value={datos.nombres}
            onChange={cambiar}
            error={errores.nombres}
          />
          <CampoTexto
            etiqueta="Apellidos"
            name="apellidos"
            autoComplete="family-name"
            requerido
            value={datos.apellidos}
            onChange={cambiar}
            error={errores.apellidos}
          />
          <Selector
            etiqueta="Tipo de documento"
            name="tipo_documento"
            opciones={OPCIONES_TIPO_DOCUMENTO}
            requerido
            value={datos.tipo_documento}
            onChange={cambiar}
            error={errores.tipo_documento}
          />
          <CampoTexto
            etiqueta="Número de documento"
            name="num_documento"
            maxLength={12}
            requerido
            value={datos.num_documento}
            onChange={cambiar}
            error={errores.num_documento}
          />
          <CampoTexto
            etiqueta="Fecha de nacimiento"
            name="fecha_nacimiento"
            type="date"
            max={fechaHoy()}
            autoComplete="bday"
            requerido
            value={datos.fecha_nacimiento}
            onChange={cambiar}
            error={errores.fecha_nacimiento}
          />
          <CampoTexto
            etiqueta="Celular"
            name="celular"
            type="tel"
            inputMode="numeric"
            autoComplete="tel-national"
            maxLength={10}
            requerido
            ayuda="10 dígitos, sin espacios. Lo usaremos para confirmar tus pedidos."
            value={datos.celular}
            onChange={cambiar}
            error={errores.celular}
          />
          <CampoTexto
            etiqueta="Correo"
            name="email"
            type="email"
            autoComplete="email"
            requerido
            value={datos.email}
            onChange={cambiar}
            error={errores.email}
          />
          <CampoTexto
            etiqueta="Contraseña"
            name="password"
            type="password"
            autoComplete="new-password"
            requerido
            ayuda="Mínimo 8 caracteres."
            value={datos.password}
            onChange={cambiar}
            error={errores.password}
          />
          <CampoTexto
            etiqueta="Confirmar contraseña"
            name="confirmarPassword"
            type="password"
            autoComplete="new-password"
            requerido
            value={datos.confirmarPassword}
            onChange={cambiar}
            error={errores.confirmarPassword}
          />

          <Boton tipo="submit" cargando={enviando}>
            Crear cuenta
          </Boton>
        </form>
      </Tarjeta>

      <p className="text-sm text-texto-suave">
        ¿Ya tienes cuenta?{' '}
        <Link to="/login" className="text-marca-clara underline underline-offset-4">
          Inicia sesión
        </Link>
      </p>
    </div>
  )
}
