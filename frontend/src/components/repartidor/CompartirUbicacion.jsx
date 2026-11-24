import { useEffect, useState } from 'react'
import { enviarUbicacion } from '../../api/repartidores.js'
import { mensajeErrorGps } from '../../utils/entregas.js'
import { INTERVALO_UBICACION_MS, llevaPedido } from '../../utils/ubicacionEntregas.js'

// HU-38 · While the courier carries an order (picked up or on the way) his phone sends
// its location every 30 s, so the branch sees him on its map. Nothing is sent otherwise.
function useCompartirUbicacion(activo) {
  const gps = typeof navigator !== 'undefined' && 'geolocation' in navigator
  const [enviada, setEnviada] = useState(false)
  const [error, setError] = useState(null)

  useEffect(() => {
    if (!activo || !gps) return undefined
    let ultima = null
    let primera = true

    const enviar = () => {
      if (!ultima) return
      enviarUbicacion(ultima)
        .then(() => {
          setEnviada(true)
          setError(null)
        })
        .catch(() => {}) // se reintenta en el siguiente intervalo
    }

    const vigilancia = navigator.geolocation.watchPosition(
      ({ coords }) => {
        ultima = { latitud: coords.latitude, longitud: coords.longitude }
        if (primera) {
          primera = false
          enviar()
        }
      },
      (fallo) => setError(mensajeErrorGps(fallo.code)),
      { enableHighAccuracy: true, timeout: 20000, maximumAge: 10000 },
    )
    const intervalo = setInterval(enviar, INTERVALO_UBICACION_MS)
    return () => {
      navigator.geolocation.clearWatch(vigilancia)
      clearInterval(intervalo)
    }
  }, [activo, gps])

  if (!activo) return { estado: 'inactivo' }
  if (!gps) return { estado: 'error', error: 'Tu navegador no permite compartir la ubicación.' }
  if (error) return { estado: 'error', error }
  return { estado: enviada ? 'compartiendo' : 'buscando' }
}

export default function CompartirUbicacion({ entregas }) {
  const { estado, error } = useCompartirUbicacion(llevaPedido(entregas))
  if (estado === 'inactivo') return null

  const estilos = {
    buscando: 'border-borde bg-superficie-alta text-texto',
    compartiendo: 'border-exito bg-exito/15 text-exito',
    error: 'border-aviso bg-aviso/15 text-aviso',
  }
  const textos = {
    buscando: 'Activando tu ubicación para que la sede vea tu recorrido…',
    compartiendo: 'Compartiendo tu ubicación con la sede mientras llevas el pedido.',
    error,
  }
  return (
    <p role="status" className={`rounded-xl border px-4 py-3 text-sm ${estilos[estado]}`}>
      <span aria-hidden="true">📍 </span>
      {textos[estado]}
    </p>
  )
}
