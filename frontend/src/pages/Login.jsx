import { Navigate, useNavigate } from 'react-router-dom'
import { useAuth } from '../auth/useAuth.js'
import { ETIQUETA_ROL, ROLES, rutaInicio } from '../auth/roles.js'
import Alerta from '../components/ui/Alerta.jsx'
import Boton from '../components/ui/Boton.jsx'
import Tarjeta from '../components/ui/Tarjeta.jsx'

// Página de inicio de sesión.
// El formulario real con el backend se construye en HU-03 y HU-04.
// Mientras tanto, en modo desarrollo se puede entrar con un rol simulado.
export default function Login() {
  const { usuario, iniciarSesionSimulada } = useAuth()
  const navegar = useNavigate()

  if (usuario) {
    return <Navigate to={rutaInicio(usuario.rol)} replace />
  }

  function entrarComo(rol) {
    iniciarSesionSimulada(rol)
    navegar(rutaInicio(rol))
  }

  return (
    <div className="mx-auto flex max-w-md flex-col gap-4">
      <h1 className="text-2xl font-bold">Iniciar sesión</h1>

      <Alerta tipo="info">
        El formulario de inicio de sesión se integra con HU-03 (clientes) y HU-04 (personal).
      </Alerta>

      {import.meta.env.DEV && (
        <Tarjeta titulo="Modo desarrollo: entrar con un rol">
          <p className="mb-3 text-sm text-texto-suave">
            Solo visible en desarrollo. Sirve para probar la navegación de cada rol.
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
