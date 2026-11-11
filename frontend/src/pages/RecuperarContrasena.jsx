import { useState } from 'react'
import { Link } from 'react-router-dom'
import { solicitarRestablecimiento } from '../api/contrasena.js'
import { interpretarError } from '../api/errores.js'
import Alerta from '../components/ui/Alerta.jsx'
import Boton from '../components/ui/Boton.jsx'
import CampoTexto from '../components/ui/CampoTexto.jsx'
import Tarjeta from '../components/ui/Tarjeta.jsx'

// HU-05 · Paso 1: la persona escribe su correo y le llega el enlace.
// El mensaje es el mismo si el correo existe o no.
export default function RecuperarContrasena() {
  const [email, setEmail] = useState('')
  const [errores, setErrores] = useState({})
  const [enviado, setEnviado] = useState(null)
  const [enviando, setEnviando] = useState(false)

  async function enviar(evento) {
    evento.preventDefault()
    if (!email.trim()) {
      setErrores({ email: 'Escribe tu correo.' })
      return
    }
    setErrores({})
    setEnviando(true)
    try {
      const { detail } = await solicitarRestablecimiento(email.trim())
      setEnviado(detail)
    } catch (fallo) {
      const { general, campos } = interpretarError(fallo)
      setErrores({ general, ...campos })
    } finally {
      setEnviando(false)
    }
  }

  return (
    <div className="mx-auto flex max-w-md flex-col gap-4">
      <h1 className="text-2xl font-bold">Recuperar contraseña</h1>

      <Tarjeta>
        {enviado ? (
          <div className="flex flex-col gap-3">
            <Alerta tipo="exito" titulo="Revisa tu correo">
              {enviado}
            </Alerta>
            <Boton variante="secundario" onClick={() => setEnviado(null)}>
              Enviar a otro correo
            </Boton>
          </div>
        ) : (
          <form noValidate onSubmit={enviar} className="flex flex-col gap-3">
            <p className="text-sm text-texto-suave">
              Escribe el correo de tu cuenta y te enviaremos un enlace para elegir una nueva contraseña.
            </p>
            {errores.general && <Alerta tipo="error" titulo={errores.general} />}
            <CampoTexto
              etiqueta="Correo"
              name="email"
              type="email"
              autoComplete="email"
              requerido
              value={email}
              error={errores.email}
              onChange={(evento) => setEmail(evento.target.value)}
            />
            <Boton tipo="submit" cargando={enviando}>
              Enviar enlace
            </Boton>
          </form>
        )}
      </Tarjeta>

      <Link to="/login" className="self-start text-marca-clara underline underline-offset-4">
        ← Volver a iniciar sesión
      </Link>
    </div>
  )
}
