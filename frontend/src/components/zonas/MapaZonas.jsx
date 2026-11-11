import { useEffect, useRef } from 'react'
import L from 'leaflet'
import { Circle, MapContainer, Polygon, TileLayer, useMap } from 'react-leaflet'
import 'leaflet/dist/leaflet.css'
import '@geoman-io/leaflet-geoman-free'
import '@geoman-io/leaflet-geoman-free/dist/leaflet-geoman.css'
import { CENTRO_CALI } from '../../api/geocodificacion.js'

const ESTILO_EDITABLE = { color: '#ff6b6b', weight: 2, fillOpacity: 0.2 }
const ESTILO_ACTIVA = { color: '#2ecc71', weight: 2, fillOpacity: 0.12 }
const ESTILO_INACTIVA = { color: '#8a8f98', weight: 1, dashArray: '6 6', fillOpacity: 0.04 }

// Convierte la capa dibujada en los campos que espera la API (radio en km).
function leerCapa(capa) {
  if (capa instanceof L.Circle) {
    const centro = capa.getLatLng()
    return {
      tipo: 'radio',
      centro_latitud: centro.lat,
      centro_longitud: centro.lng,
      radio: capa.getRadius() / 1000, // Geoman da metros; la API espera km
    }
  }
  const anillo = capa.getLatLngs()[0]
  return { tipo: 'poligono', poligono_vertices: anillo.map((p) => [p.lat, p.lng]) }
}

// Controles de dibujo (Geoman) para UNA zona: círculo o polígono.
// Dibujar una forma nueva reemplaza la anterior. `alCambiar(forma | null)`.
function EditorForma({ formaInicial, alCambiar }) {
  const mapa = useMap()
  const capaActual = useRef(null)
  const callback = useRef(alCambiar)

  useEffect(() => {
    callback.current = alCambiar
  }, [alCambiar])

  useEffect(() => {
    mapa.pm.addControls({
      position: 'topleft',
      drawMarker: false,
      drawCircleMarker: false,
      drawPolyline: false,
      drawRectangle: false,
      drawText: false,
      drawCircle: true,
      drawPolygon: true,
      editMode: true,
      dragMode: true,
      cutPolygon: false,
      rotateMode: false,
      removalMode: true,
    })
    mapa.pm.setGlobalOptions({ pathOptions: ESTILO_EDITABLE, allowSelfIntersection: false })

    const adjuntar = (capa, avisar) => {
      capaActual.current = capa
      const alEditar = () => callback.current(leerCapa(capa))
      capa.on('pm:edit', alEditar)
      capa.on('pm:dragend', alEditar)
      if (avisar) callback.current(leerCapa(capa))
    }

    const alCrear = (evento) => {
      if (capaActual.current) mapa.removeLayer(capaActual.current)
      adjuntar(evento.layer, true)
    }
    const alQuitar = (evento) => {
      if (evento.layer === capaActual.current) {
        capaActual.current = null
        callback.current(null)
      }
    }
    mapa.on('pm:create', alCrear)
    mapa.on('pm:remove', alQuitar)

    if (formaInicial?.tipo === 'radio') {
      const capa = L.circle([formaInicial.centro_latitud, formaInicial.centro_longitud], {
        ...ESTILO_EDITABLE,
        radius: formaInicial.radio * 1000,
      }).addTo(mapa)
      adjuntar(capa, false)
      mapa.fitBounds(capa.getBounds())
    } else if (formaInicial?.tipo === 'poligono') {
      const capa = L.polygon(formaInicial.poligono_vertices, ESTILO_EDITABLE).addTo(mapa)
      adjuntar(capa, false)
      mapa.fitBounds(capa.getBounds())
    }

    return () => {
      mapa.off('pm:create', alCrear)
      mapa.off('pm:remove', alQuitar)
      mapa.pm.removeControls()
      mapa.pm.disableDraw()
      if (capaActual.current) mapa.removeLayer(capaActual.current)
      capaActual.current = null
    }
  }, [mapa, formaInicial])

  return null
}

// Mapa para delimitar una zona (HU-55).
// - formaInicial: forma de la zona que se edita (o null si es nueva).
// - otras: zonas ya existentes de la sede, solo para ver (en gris).
// Conviene usar `key` en el padre para reiniciar el mapa al cambiar de zona.
export default function MapaZonas({ formaInicial, otras = [], centro, alCambiar }) {
  return (
    <div className="isolate overflow-hidden rounded-lg border border-borde">
      <MapContainer
        center={centro ?? CENTRO_CALI}
        zoom={13}
        className="h-[28rem] w-full"
        aria-label="Mapa para delimitar la zona de cobertura"
      >
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />
        {otras.map((zona) =>
          zona.tipo === 'poligono' ? (
            <Polygon key={zona.id} positions={zona.poligono_vertices} pathOptions={zona.activo ? ESTILO_ACTIVA : ESTILO_INACTIVA} />
          ) : (
            <Circle
              key={zona.id}
              center={[zona.centro_latitud, zona.centro_longitud]}
              radius={zona.radio * 1000}
              pathOptions={zona.activo ? ESTILO_ACTIVA : ESTILO_INACTIVA}
            />
          ),
        )}
        <EditorForma formaInicial={formaInicial} alCambiar={alCambiar} />
      </MapContainer>
      <p className="flex gap-4 border-t border-borde bg-superficie px-3 py-2 text-xs text-texto-suave">
        <span><span className="text-exito">●</span> Zona activa</span>
        <span>○ Zona desactivada</span>
      </p>
    </div>
  )
}