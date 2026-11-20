import { useEffect, useState } from 'react'

export const DURACION_MENSAJE_MS = 5000

// Like useState for a page message ({ tipo, texto }), but it clears itself after a few
// seconds so success and error banners do not stay on screen forever.
export function useMensajeTemporal(duracionMs = DURACION_MENSAJE_MS) {
  const [mensaje, setMensaje] = useState(null)

  useEffect(() => {
    if (!mensaje) return undefined
    const temporizador = setTimeout(() => setMensaje(null), duracionMs)
    return () => clearTimeout(temporizador)
  }, [mensaje, duracionMs])

  return [mensaje, setMensaje]
}
