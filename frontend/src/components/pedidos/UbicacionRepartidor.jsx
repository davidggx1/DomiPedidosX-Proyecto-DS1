import { useEffect, useRef, useState } from 'react'
import L from 'leaflet'
import { CircleMarker, MapContainer, Marker, Polyline, TileLayer, Tooltip, useMap } from 'react-leaflet'
import 'leaflet/dist/leaflet.css'
import iconoMarcador from 'leaflet/dist/images/marker-icon.png'
import iconoMarcador2x from 'leaflet/dist/images/marker-icon-2x.png'
import sombraMarcador from 'leaflet/dist/images/marker-shadow.png'
import { obtenerUbicacionMiPedido } from '../../api/pedidos.js'
import Tarjeta from '../ui/Tarjeta.jsx'
import { INTERVALO_UBICACION_MS, textoUbicacionCliente } from '../../utils/ubicacionEntregas.js'

// Con Vite, Leaflet no encuentra sus íconos por defecto: se le pasan importados (igual que en HU-44).
const ICONO_CASA = L.icon({
  iconUrl: iconoMarcador,
  iconRetinaUrl: iconoMarcador2x,
  shadowUrl: sombraMarcador,
  iconSize: [25, 41],
  iconAnchor: [12, 41],
  shadowSize: [41, 41],
})

const COLOR_REPARTIDOR = '#16a34a'

// Encuadra repartidor y destino solo la primera vez que ambos existen,
// para no mover el mapa si el cliente lo acercó a mano.
function Encuadrar({ puntos }) {
  const mapa = useMap()
  const hecho = useRef(false)
  useEffect(() => {
    if (hecho.current || puntos.length === 0) return
    if (puntos.length === 1) mapa.setView(puntos[0], 15, { animate: false })
    else mapa.fitBounds(puntos, { padding: [40, 40], maxZoom: 16, animate: false })
    hecho.current = puntos.length > 1
  }, [mapa, puntos])
  return null
}

function Mapa({ datos }) {
  const repartidor = datos.ubicacion && [datos.ubicacion.latitud, datos.ubicacion.longitud]
  const casa = datos.destino && [datos.destino.latitud, datos.destino.longitud]
  const puntos = [repartidor, casa].filter(Boolean)
  const opacidad = datos.sin_senal ? 0.35 : 0.95
  return (
    <div className="h-72 overflow-hidden rounded-xl border border-borde sm:h-80">
      <MapContainer center={puntos[0]} zoom={15} className="h-full w-full">
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />
        <Encuadrar puntos={puntos} />
        {repartidor && casa && (
          <Polyline
            positions={[repartidor, casa]}
            pathOptions={{ color: COLOR_REPARTIDOR, weight: 2, dashArray: '6 6', opacity: opacidad }}
          />
        )}
        {casa && (
          <Marker position={casa} icon={ICONO_CASA}>
            <Tooltip direction="top" offset={[0, -36]}>
              Tu dirección
            </Tooltip>
          </Marker>
        )}
        {repartidor && (
          <CircleMarker
            center={repartidor}
            radius={10}
            pathOptions={{ color: COLOR_REPARTIDOR, fillColor: COLOR_REPARTIDOR, fillOpacity: opacidad, opacity: opacidad }}
          >
            <Tooltip direction="right" permanent>
              🛵 {datos.repartidor ?? 'Repartidor'}
            </Tooltip>
          </CircleMarker>
        )}
      </MapContainer>
    </div>
  )
}

// HU-49 · Mientras el pedido está "En camino", el cliente ve en un mapa dónde va el
// repartidor. Se pregunta cada 30 s (el ritmo con que el celular del repartidor la envía)
// y deja de hacerlo en cuanto el pedido cambia de estado.
export default function UbicacionRepartidor({ pedidoId, estado }) {
  const activo = estado === 'en_camino'
  const [datos, setDatos] = useState(null)
  const [ahora, setAhora] = useState(null)

  useEffect(() => {
    if (!activo) return undefined
    let vigente = true
    function cargar() {
      obtenerUbicacionMiPedido(pedidoId)
        .then((respuesta) => {
          if (!vigente) return
          setDatos(respuesta)
          setAhora(Date.now())
        })
        // un fallo puntual no se muestra: el siguiente intento lo corrige
        .catch(() => {})
    }
    cargar()
    const temporizador = setInterval(cargar, INTERVALO_UBICACION_MS)
    return () => {
      vigente = false
      clearInterval(temporizador)
    }
  }, [pedidoId, activo])

  if (!activo || !datos?.rastreando) return null
  const hayPuntos = datos.ubicacion || datos.destino

  return (
    <Tarjeta titulo="¿Dónde va tu pedido?">
      <div className="flex flex-col gap-3">
        {hayPuntos && <Mapa datos={datos} />}
        <p aria-live="polite" className={`text-sm ${datos.sin_senal ? 'text-aviso' : 'text-texto-suave'}`}>
          {textoUbicacionCliente(datos, ahora)}
        </p>
      </div>
    </Tarjeta>
  )
}
