import { useEffect, useState } from 'react'
import { Link, Navigate, useNavigate } from 'react-router-dom'
import { ErrorInicioSesion, autenticar } from '../api/auth.js'
import { interpretarError } from '../api/errores.js'
import { useAuth } from '../auth/useAuth.js'
import { ETIQUETA_ROL, ROLES, rutaInicio } from '../auth/roles.js'
import { consumirAvisoSesionExpirada } from '../auth/sesionGuardada.js'
import Alerta from '../components/ui/Alerta.jsx'
import Boton from '../components/ui/Boton.jsx'
import CampoTexto from '../components/ui/CampoTexto.jsx'
import Tarjeta from '../components/ui/Tarjeta.jsx'

// Segundos de espera antes de avisar que el servidor puede estar despertando
const SEGUNDOS_AVISO_DESPERTAR = 5

// Página de inicio de sesión (HU-03 clientes y HU-04 personal).
// Un solo formulario: el backend dice si la cuenta es de cliente o de personal y su rol.
export default function Login() {
  const { usuario, iniciarSesion, iniciarSesionSimulada } = useAuth()
  const navegar = useNavigate()
  const [credenciales, setCredenciales] = useState({ email: '', password: '' })
  const [error, setError] = useState(null)
  const [enviando, setEnviando] = useState(false)
  const [tardando, setTardando] = useState(false)
  const [sesionExpirada] = useState(consumirAvisoSesionExpirada)

  useEffect(() => {
    if (!enviando) return undefined
    const temporizador = setTimeout(() => setTardando(true), SEGUNDOS_AVISO_DESPERTAR * 1000)
    return () => clearTimeout(temporizador)
  }, [enviando])

  if (usuario) {
    return <Navigate to={rutaInicio(usuario.rol)} replace />
  }

  function entrarComo(rol) {
    iniciarSesionSimulada(rol)
    navegar(rutaInicio(rol))
  }

  function cambiar(evento) {
    const { name, value } = evento.target
    setCredenciales((actuales) => ({ ...actuales, [name]: value }))
    setError(null)
  }

  async function entrar(evento) {
    evento.preventDefault()
    if (!credenciales.email.trim() || !credenciales.password) {
      setError('Escribe tu correo y tu contraseña.')
      return
    }
    setError(null)
    setEnviando(true)
    try {
      const sesion = await autenticar(credenciales.email, credenciales.password)
      iniciarSesion(sesion)
      navegar(rutaInicio(sesion.usuario.rol), { replace: true })
    } catch (fallo) {
      setError(
        fallo instanceof ErrorInicioSesion
          ? fallo.message
          : (interpretarError(fallo).general ?? 'No se pudo iniciar sesión. Intenta de nuevo.'),
      )
    } finally {
      setEnviando(false)
      setTardando(false)
    }
  }

  return (
    <div className="mx-auto flex max-w-md flex-col gap-4">
      <h1 className="text-2xl font-bold">Iniciar sesión</h1>

      {sesionExpirada && (
        <Alerta tipo="info" titulo="Tu sesión expiró">
          Vuelve a iniciar sesión para continuar.
        </Alerta>
      )}

      <Tarjeta>
        <form noValidate onSubmit={entrar} className="flex flex-col gap-3">
          {error && <Alerta tipo="error" titulo={error} />}
          <CampoTexto
            etiqueta="Correo"
            name="email"
            type="email"
            autoComplete="username"
            value={credenciales.email}
            onChange={cambiar}
          />
          <CampoTexto
            etiqueta="Contraseña"
            name="password"
            type="password"
            autoComplete="current-password"
            value={credenciales.password}
            onChange={cambiar}
          />
          <Boton tipo="submit" cargando={enviando}>
            Iniciar sesión
          </Boton>
          {tardando && (
            <p className="text-sm text-texto-suave" role="status">
              El servidor está despertando, puede tardar hasta un minuto la primera vez…
            </p>
          )}
        </form>
      </Tarjeta>

      <Link to="/recuperar-contrasena" className="self-start text-marca-clara underline underline-offset-4">
        ¿Olvidaste tu contraseña?
      </Link>

      <p className="text-sm text-texto-suave">
        ¿No tienes cuenta?{' '}
        <Link to="/registro" className="text-marca-clara underline underline-offset-4">
          Crear cuenta
        </Link>
      </p>

      {import.meta.env.DEV && (
        <Tarjeta titulo="Modo desarrollo: entrar con un rol simulado">
          <p className="mb-3 text-sm text-texto-suave">
            Sin conexión con el backend. Sirve para probar la navegación de cada rol. No aparece en producción.
          </p>
          <div className="flex flex-col gap-2">
            {Object.values(ROLES).map((rol) => (
              <Boton key={rol} variante="secundario" onClick={() => entrarComo(rol)}>
                Entrar como {ETIQUETA_ROL[rol]}
              </Boton>
            ))}
          </div>
        </Tarjeta>
      )}
    </div>
  )
}
