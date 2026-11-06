import { Navigate } from 'react-router-dom'
import { useAuth } from '../auth/useAuth.js'
import { rutaInicio } from '../auth/roles.js'

// La raíz "/" lleva a cada usuario a la página principal de su rol.
export default function Inicio() {
  const { usuario } = useAuth()
  return <Navigate to={usuario ? rutaInicio(usuario.rol) : '/login'} replace />
}
