import { useEffect, useRef, useState } from 'react'
import L from 'leaflet'
import { Circle, CircleMarker, MapContainer, Marker, Polyline, TileLayer, Tooltip, useMap } from 'react-leaflet'
import 'leaflet/dist/leaflet.css'
import iconoMarcador from 'leaflet/dist/images/marker-icon.png'
import iconoMarcador2x from 'leaflet/dist/images/marker-icon-2x.png'
import sombraMarcador from 'leaflet/dist/images/marker-shadow.png'
import { enlaceRuta, mensajeErrorGps } from '../../utils/entregas.js'
import Alerta from '../ui/Alerta.jsx'
import Boton from '../ui/Boton.jsx'

// Con Vite, Leaflet no encuentra sus íconos por defecto: se le pasan importados (igual que en HU-06).
const ICONO_CLIENTE = L.icon({
  iconUrl: iconoMarcador,
  iconRetinaUrl: iconoMarcador2x,
  shadowUrl: sombraMarcador,
  iconSize: [25, 41],
  iconAnchor: [12, 41],
  shadowSize: [41, 41],
})

const COLOR_SEDE = '#ff6b6b'
const COLOR_REPARTIDOR = '#4ade80'

// Encuadra el mapa para que se vean el cliente y el punto de partida.
// Lo hace al abrir (con la sede) y otra vez cuando llega la primera lectura del GPS.
// No lo repite con cada lectura: el repartidor debe poder acercar el mapa a mano.
function Encuadrar({ puntos, clave }) {
  const mapa = useMap()
  const ultimaClave = useRef(null)
  useEffect(() => {
    if (ultimaClave.current === clave || puntos.length < 2) return
    mapa.fitBounds(puntos, { padding: [40, 40], maxZoom: 16, animate: false })
    ultimaClave.current = clave
  }, [mapa, puntos, clave])
  return null
}

// Sigue la posición del repartidor mientras el mapa está abierto.
function useUbicacionRepartidor() {
  const disponible = typeof navigator !== 'undefined' && 'geolocation' in navigator
  const [estado, setEstado] = useState(() =>
    disponible
      ? { posicion: null, precision: null, error: null }
      : { posicion: null, precision: null, error: 'Tu navegador no permite obtener la ubicación.' },
  )

  useEffect(() => {
    if (!disponible) return undefined
    const vigilancia = navigator.geolocation.watchPosition(
      ({ coords }) =>
        setEstado({
          posicion: { latitud: coords.latitude, longitud: coords.longitude },
          precision: coords.accuracy,
          error: null,
        }),
      (fallo) => setEstado((anterior) => ({ ...anterior, error: mensajeErrorGps(fallo.code) })),
      { enableHighAccuracy: true, timeout: 15000, maximumAge: 10000 },
    )
    return () => navigator.geolocation.clearWatch(vigilancia)
  }, [disponible])

  return estado
}

// El mapa en sí. Se monta solo al abrirlo, así el GPS se pide cuando hace falta.
function MapaAbierto({ entrega }) {
  const { posicion, precision, error: errorGps } = useUbicacionRepartidor()
  const [errorMapa, setErrorMapa] = useState(false)

  const cliente = [entrega.entrega_latitud, entrega.entrega_longitud]
  const sede = entrega.punto_recogida
  const puntoSede = sede ? [sede.latitud, sede.longitud] : null
  const puntoRepartidor = posicion ? [posicion.latitud, posicion.longitud] : null
  // La línea parte del repartidor; mientras no haya GPS, de la sede.
  const partida = puntoRepartidor ?? puntoSede
  const origenRuta = posicion ?? (sede ? { latitud: sede.latitud, longitud: sede.longitud } : null)

  return (
    <div className="flex flex-col gap-3">
      {errorGps && <Alerta tipo="aviso" titulo={errorGps} />}
      {errorMapa && (
        <Alerta tipo="aviso" titulo="El mapa no cargó completo. Revisa tu conexión; la dirección está arriba." />
      )}

      {/* `isolate` evita que las capas de Leaflet queden por encima del menú de la página. */}
      <div className="isolate overflow-hidden rounded-lg border border-borde">
        <MapContainer center={cliente} zoom={16} className="h-80 w-full" aria-label="Mapa con la dirección del cliente">
          <TileLayer
            attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
            url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
            eventHandlers={{ tileerror: () => setErrorMapa(true) }}
          />
          <Encuadrar puntos={partida ? [cliente, partida] : [cliente]} clave={puntoRepartidor ? 'gps' : 'sede'} />

          <Marker position={cliente} icon={ICONO_CLIENTE}>
            <Tooltip permanent direction="top" offset={[0, -36]}>
              Cliente
            </Tooltip>
          </Marker>

          {puntoSede && (
            <CircleMarker center={puntoSede} radius={8} pathOptions={{ color: COLOR_SEDE, fillOpacity: 0.9 }}>
              <Tooltip>Sede: {sede.nombre}</Tooltip>
            </CircleMarker>
          )}

          {puntoRepartidor && (
            <>
              {precision && (
                <Circle
                  center={puntoRepartidor}
                  radius={precision}
                  pathOptions={{ color: COLOR_REPARTIDOR, weight: 1, fillOpacity: 0.1 }}
                />
              )}
              <CircleMarker
                center={puntoRepartidor}
                radius={8}
                pathOptions={{ color: COLOR_REPARTIDOR, fillOpacity: 0.9 }}
              >
                <Tooltip>Tú estás aquí</Tooltip>
              </CircleMarker>
            </>
          )}

          {partida && (
            <Polyline positions={[partida, cliente]} pathOptions={{ color: COLOR_SEDE, dashArray: '6 8', weight: 3 }} />
          )}
        </MapContainer>
      </div>

      <p className="text-sm text-texto-suave">
        <span style={{ color: COLOR_REPARTIDOR }}>●</span> Tú · <span style={{ color: COLOR_SEDE }}>●</span> Sede · pin
        azul: cliente. La línea punteada es la distancia en línea recta, no la ruta.
      </p>

      <a
        href={enlaceRuta(entrega, origenRuta)}
        target="_blank"
        rel="noreferrer"
        className="inline-flex min-h-11 items-center justify-center rounded-lg bg-marca px-4 py-2 font-medium text-sobre-marca hover:bg-marca-oscura"
      >
        Cómo llegar (abrir navegación)
      </a>
    </div>
  )
}

// HU-44 · Dirección del cliente en el mapa.
// La dirección escrita la muestra siempre la página de detalle; este componente
// solo agrega el mapa, así que si el mapa o el GPS fallan el repartidor no se queda sin guía.
export default function MapaEntrega({ entrega }) {
  const [abierto, setAbierto] = useState(false)

  if (!entrega.tiene_ubicacion) {
    return (
      <div className="flex flex-col gap-3">
        <Alerta tipo="info" titulo="Esta dirección no tiene ubicación en el mapa.">
          Guíate por la dirección escrita o llama al cliente.
        </Alerta>
        <a
          href={enlaceRuta(entrega)}
          target="_blank"
          rel="noreferrer"
          className="self-start text-marca-clara underline underline-offset-4"
        >
          Buscar la dirección en Google Maps
        </a>
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-3">
      <Boton
        variante="secundario"
        onClick={() => setAbierto((valor) => !valor)}
        aria-expanded={abierto}
        className="self-start"
      >
        {abierto ? 'Ocultar mapa' : 'Ver en el mapa'}
      </Boton>
      {abierto && <MapaAbierto entrega={entrega} />}
    </div>
  )
}
