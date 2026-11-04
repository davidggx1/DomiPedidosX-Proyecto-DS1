import { useEffect } from 'react'
import L from 'leaflet'
import { Circle, MapContainer, Marker, TileLayer, useMap, useMapEvents } from 'react-leaflet'
import 'leaflet/dist/leaflet.css'
import iconoMarcador from 'leaflet/dist/images/marker-icon.png'
import iconoMarcador2x from 'leaflet/dist/images/marker-icon-2x.png'
import sombraMarcador from 'leaflet/dist/images/marker-shadow.png'
import { CENTRO_CALI } from '../../api/geocodificacion.js'

// Con Vite, Leaflet no encuentra sus íconos por defecto: se le pasan importados.
const ICONO = L.icon({
  iconUrl: iconoMarcador,
  iconRetinaUrl: iconoMarcador2x,
  shadowUrl: sombraMarcador,
  iconSize: [25, 41],
  iconAnchor: [12, 41],
  shadowSize: [41, 41],
})

// Clic en el mapa: mueve el pin a ese punto.
function AlHacerClic({ alCambiar }) {
  useMapEvents({
    click: (evento) => alCambiar(evento.latlng.lat, evento.latlng.lng),
  })
  return null
}

// Lleva la vista al punto indicado (búsqueda, ubicación actual o dirección que se edita).
// `enfoque.zoom` permite alejar la vista cuando la ubicación es poco precisa.
// Sin animación: si el pin cambia mientras anima el zoom (p. ej. al deshacer),
// Leaflet corta la animación y la vista no llega al punto.
function Enfocar({ enfoque }) {
  const mapa = useMap()
  useEffect(() => {
    if (enfoque) mapa.setView([enfoque.latitud, enfoque.longitud], enfoque.zoom ?? 17, { animate: false })
  }, [mapa, enfoque])
  return null
}

// Mapa para ubicar una dirección (HU-06).
// - posicion: { latitud, longitud } del pin, o null si aún no se ubica.
// - enfoque: punto al que mover la vista; cambia solo al buscar o al abrir una dirección.
// - precision: radio en metros de la ubicación actual del dispositivo (se dibuja un círculo).
// - alCambiar(latitud, longitud): se llama al hacer clic o al soltar el pin.
export default function MapaUbicacion({ posicion, enfoque, precision, alCambiar }) {
  const eventosMarcador = {
    dragend: (evento) => {
      const { lat, lng } = evento.target.getLatLng()
      alCambiar(lat, lng)
    },
  }

  return (
    // `isolate` evita que las capas de Leaflet queden por encima del menú de la página.
    <div className="isolate overflow-hidden rounded-lg border border-borde">
      <MapContainer
        center={enfoque ? [enfoque.latitud, enfoque.longitud] : CENTRO_CALI}
        zoom={enfoque ? 17 : 13}
        className="h-80 w-full"
        aria-label="Mapa para ubicar la dirección"
      >
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />
        <AlHacerClic alCambiar={alCambiar} />
        <Enfocar enfoque={enfoque} />
        {posicion && precision && (
          <Circle
            center={[posicion.latitud, posicion.longitud]}
            radius={precision}
            pathOptions={{ color: '#ff6b6b', weight: 1, fillOpacity: 0.12 }}
          />
        )}
        {posicion && (
          <Marker
            position={[posicion.latitud, posicion.longitud]}
            icon={ICONO}
            draggable
            eventHandlers={eventosMarcador}
          />
        )}
      </MapContainer>
    </div>
  )
}
