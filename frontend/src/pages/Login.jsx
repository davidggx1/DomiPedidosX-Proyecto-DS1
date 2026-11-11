import { useState } from 'react'
import { Link, Navigate, useNavigate } from 'react-router-dom'
import api from '../api/cliente.js'
import { interpretarError } from '../api/errores.js'
import { useAuth } from '../auth/useAuth.js'
import { ETIQUETA_ROL, ROLES, rutaInicio } from '../auth/roles.js'
import Alerta from '../components/ui/Alerta.jsx'
import Boton from '../components/ui/Boton.jsx'
import CampoTexto from '../components/ui/CampoTexto.jsx'
import Selector from '../components/ui/Selector.jsx'
import Tarjeta from '../components/ui/Tarjeta.jsx'

const OPCIONES_ROL = Object.values(ROLES).map((rol) => ({ valor: rol, etiqueta: ETIQUETA_ROL[rol] }))

// Página de inicio de sesión.
// El formulario real con el backend se construye en HU-03 y HU-04.
// Mientras tanto, en modo desarrollo se puede entrar con un rol simulado
// o pedir un token real al backend para probar las pantallas que usan la API.
export default function Login() {
  const { usuario, iniciarSesion, iniciarSesionSimulada } = useAuth()
  const navegar = useNavigate()
  const [credenciales, setCredenciales] = useState({ email: '', password: '', rol: ROLES.OPERADOR })
  const [errorConexion, setErrorConexion] = useState(null)
  const [conectando, setConectando] = useState(false)

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
  }

  async function conectarConBackend(evento) {
    evento.preventDefault()
    setErrorConexion(null)
    setConectando(true)
    try {
      const { data } = await api.post('/auth/token/', {
        email: credenciales.email,
        password: credenciales.password,
      })
      iniciarSesion({
        token: data.access,
        usuario: { nombre: credenciales.email, email: credenciales.email, rol: credenciales.rol },
      })
      navegar(rutaInicio(credenciales.rol))
    } catch (error) {
      setErrorConexion(
        error.response?.status === 401
          ? 'Correo o contraseña incorrectos.'
          : interpretarError(error).general,
      )
    } finally {
      setConectando(false)
    }
  }

  return (
    <div className="mx-auto flex max-w-md flex-col gap-4">
      <h1 className="text-2xl font-bold">Iniciar sesión</h1>

      <Alerta tipo="info">
        El formulario de inicio de sesión se integra con HU-03 (clientes) y HU-04 (personal).
      </Alerta>

      <Link to="/recuperar-contrasena" className="self-start text-marca-clara underline underline-offset-4">
        ¿Olvidaste tu contraseña?
      </Link>

      {import.meta.env.DEV && (
        <>
          <Tarjeta titulo="Modo desarrollo: conectar con el backend">
            <p className="mb-3 text-sm text-texto-suave">
              Pide un token real a Django para probar las pantallas que usan la API. Usa una cuenta
              de tu base local, por ejemplo la del administrador creado por seed_datos.
            </p>
            <form noValidate onSubmit={conectarConBackend} className="flex flex-col gap-3">
              {errorConexion && <Alerta tipo="error" titulo={errorConexion} />}
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
              <Selector
                etiqueta="Ver la aplicación como"
                name="rol"
                opciones={OPCIONES_ROL}
                value={credenciales.rol}
                onChange={cambiar}
              />
              <Boton tipo="submit" cargando={conectando}>
                Conectar
              </Boton>
            </form>
          </Tarjeta>

          <Tarjeta titulo="Modo desarrollo: entrar con un rol simulado">
            <p className="mb-3 text-sm text-texto-suave">
              Sin conexión con el backend. Sirve para probar la navegación de cada rol.
            </p>
            <div className="flex flex-col gap-2">
              {Object.values(ROLES).map((rol) => (
                <Boton key={rol} variante="secundario" onClick={() => entrarComo(rol)}>
                  Entrar como {ETIQUETA_ROL[rol]}
                </Boton>
              ))}
            </div>
          </Tarjeta>
        </>
      )}
    </div>
  )
}
