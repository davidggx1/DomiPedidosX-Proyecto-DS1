import { Navigate, Outlet, useLocation } from 'react-router-dom'
import { useAuth } from './useAuth.js'

// Protege un grupo de rutas:
// - Sin sesión: redirige al login.
// - Con sesión pero con otro rol: redirige a "No autorizado".
export default function RutaProtegida({ roles }) {
  const { usuario } = useAuth()
  const ubicacion = useLocation()

  if (!usuario) {
    return <Navigate to="/login" replace state={{ desde: ubicacion.pathname }} />
  }

  if (roles && !roles.includes(usuario.rol)) {
    return <Navigate to="/no-autorizado" replace />
  }

  return <Outlet />
}
