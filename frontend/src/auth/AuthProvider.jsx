import { useCallback, useEffect, useMemo, useState } from 'react'
import { AuthContext } from './AuthContext.js'
import { EVENTO_SESION, guardarSesion, leerSesion } from './sesionGuardada.js'
import { ETIQUETA_ROL } from './roles.js'

// Maneja la sesión del usuario en todo el frontend.
// iniciarSesion recibe la sesión del login real (api/auth.js). iniciarSesionSimulada
// solo se usa en modo desarrollo para recorrer la navegación de cada rol.
export default function AuthProvider({ children }) {
  const [sesion, setSesion] = useState(leerSesion)

  // El cliente de Axios renueva el token o cierra la sesión expirada por su cuenta
  useEffect(() => {
    const recargar = () => setSesion(leerSesion())
    window.addEventListener(EVENTO_SESION, recargar)
    return () => window.removeEventListener(EVENTO_SESION, recargar)
  }, [])

  const actualizarSesion = useCallback((nueva) => {
    setSesion(nueva)
    guardarSesion(nueva)
  }, [])

  // Para el login real: recibe { token, refresh, usuario: { nombre, email, rol, sede } }.
  const iniciarSesion = useCallback(
    (datosSesion) => actualizarSesion(datosSesion),
    [actualizarSesion],
  )

  const iniciarSesionSimulada = useCallback(
    (rol) =>
      actualizarSesion({
        token: null,
        usuario: {
          nombre: `${ETIQUETA_ROL[rol]} de prueba`,
          email: `${rol}@prueba.local`,
          rol,
        },
      }),
    [actualizarSesion],
  )

  const cerrarSesion = useCallback(() => actualizarSesion(null), [actualizarSesion])

  // Cambia datos del usuario sin cerrar la sesión (HU-07: el nombre del encabezado).
  const actualizarUsuario = useCallback((cambios) => {
    setSesion((actual) => {
      if (!actual) return actual
      const nueva = { ...actual, usuario: { ...actual.usuario, ...cambios } }
      guardarSesion(nueva)
      return nueva
    })
  }, [])

  const valor = useMemo(
    () => ({
      usuario: sesion?.usuario ?? null,
      token: sesion?.token ?? null,
      iniciarSesion,
      iniciarSesionSimulada,
      cerrarSesion,
      actualizarUsuario,
    }),
    [sesion, iniciarSesion, iniciarSesionSimulada, cerrarSesion, actualizarUsuario],
  )

  return <AuthContext.Provider value={valor}>{children}</AuthContext.Provider>
}
