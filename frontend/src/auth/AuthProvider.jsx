import { useCallback, useMemo, useState } from 'react'
import { AuthContext } from './AuthContext.js'
import { guardarSesion, leerSesion } from './sesionGuardada.js'
import { ETIQUETA_ROL } from './roles.js'

// Maneja la sesión del usuario en todo el frontend.
// Mientras el login real (HU-03 y HU-04) no esté integrado, existe
// iniciarSesionSimulada para probar la navegación de cada rol en desarrollo.
export default function AuthProvider({ children }) {
  const [sesion, setSesion] = useState(leerSesion)

  const actualizarSesion = useCallback((nueva) => {
    setSesion(nueva)
    guardarSesion(nueva)
  }, [])

  // Para el login real: recibe { token, usuario: { nombre, email, rol, sede } }.
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

  const valor = useMemo(
    () => ({
      usuario: sesion?.usuario ?? null,
      token: sesion?.token ?? null,
      iniciarSesion,
      iniciarSesionSimulada,
      cerrarSesion,
    }),
    [sesion, iniciarSesion, iniciarSesionSimulada, cerrarSesion],
  )

  return <AuthContext.Provider value={valor}>{children}</AuthContext.Provider>
}
