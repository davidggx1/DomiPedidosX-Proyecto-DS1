import { Fragment, useCallback, useEffect, useRef, useState } from 'react'
import L from 'leaflet'
import { CircleMarker, MapContainer, Marker, Polyline, TileLayer, Tooltip, useMap } from 'react-leaflet'
import 'leaflet/dist/leaflet.css'
import iconoMarcador from 'leaflet/dist/images/marker-icon.png'
import iconoMarcador2x from 'leaflet/dist/images/marker-icon-2x.png'
import sombraMarcador from 'leaflet/dist/images/marker-shadow.png'
import { interpretarError } from '../../api/errores.js'
import { obtenerMapaEnCamino } from '../../api/pedidos.js'
import Alerta from '../../components/ui/Alerta.jsx'
import Boton from '../../components/ui/Boton.jsx'
import Tarjeta from '../../components/ui/Tarjeta.jsx'
import { puntosDelMapa, textoUbicacion } from '../../utils/ubicacionEntregas.js'

// Con Vite, Leaflet no encuentra sus íconos por defecto: se le pasan importados (igual que en HU-44).
const ICONO_DESTINO = L.icon({
  iconUrl: iconoMarcador,
  iconRetinaUrl: iconoMarcador2x,
  shadowUrl: sombraMarcador,
  iconSize: [25, 41],
  iconAnchor: [12, 41],
  shadowSize: [41, 41],
})

const COLOR_SEDE = '#ff6b6b'
const COLOR_REPARTIDOR = '#16a34a'
const CENTRO_CALI = [3.4516, -76.532]

// Encuadra el mapa cuando cambia el conjunto de pedidos, no en cada actualización:
// así el operador puede acercar el mapa a mano sin que salte cada 30 segundos.
function Encuadrar({ puntos, clave }) {
  const mapa = useMap()
  const ultimaClave = useRef(null)
  useEffect(() => {
    if (ultimaClave.current === clave || puntos.length === 0) return
    if (puntos.length === 1) mapa.setView(puntos[0], 15, { animate: false })
    else mapa.fitBounds(puntos, { padding: [40, 40], maxZoom: 16, animate: false })
    ultimaClave.current = clave
  }, [mapa, puntos, clave])
  return null
}

function MapaEnCamino({ datos }) {
  const sede = datos.sede?.ubicacion
  const puntos = puntosDelMapa(datos)
  const clave = datos.entregas.map((e) => e.pedido_id).join(',')
  return (
    <div className="h-[420px] overflow-hidden rounded-xl border border-borde sm:h-[520px]">
      <MapContainer center={sede ? [sede.latitud, sede.longitud] : CENTRO_CALI} zoom={14} className="h-full w-full">
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />
        <Encuadrar puntos={puntos} clave={clave} />
        {sede && (
          <CircleMarker
            center={[sede.latitud, sede.longitud]}
            radius={10}
            pathOptions={{ color: COLOR_SEDE, fillColor: COLOR_SEDE, fillOpacity: 0.9 }}
          >
            <Tooltip direction="top">{datos.sede.nombre}</Tooltip>
          </CircleMarker>
        )}
        {datos.entregas.map((entrega) => {
          const repartidor = entrega.ubicacion && [entrega.ubicacion.latitud, entrega.ubicacion.longitud]
          const destino = entrega.destino && [entrega.destino.latitud, entrega.destino.longitud]
          const opacidad = entrega.sin_senal ? 0.35 : 0.95
          return (
            <Fragment key={entrega.pedido_id}>
              {repartidor && destino && (
                <Polyline
                  positions={[repartidor, destino]}
                  pathOptions={{ color: COLOR_REPARTIDOR, weight: 2, dashArray: '6 6', opacity: opacidad }}
                />
              )}
              {destino && (
                <Marker position={destino} icon={ICONO_DESTINO}>
                  <Tooltip direction="top" offset={[0, -36]}>
                    {entrega.numero_pedido} · {entrega.destino_direccion}
                  </Tooltip>
                </Marker>
              )}
              {repartidor && (
                <CircleMarker
                  center={repartidor}
                  radius={9}
                  pathOptions={{
                    color: COLOR_REPARTIDOR,
                    fillColor: COLOR_REPARTIDOR,
                    fillOpacity: opacidad,
                    opacity: opacidad,
                  }}
                >
                  <Tooltip direction="right" permanent>
                    🛵 {entrega.numero_pedido}
                  </Tooltip>
                </CircleMarker>
              )}
            </Fragment>
          )
        })}
      </MapContainer>
    </div>
  )
}

function FilaEntrega({ entrega, ahora }) {
  return (
    <li className="flex flex-col gap-1 rounded-xl border border-borde bg-fondo p-3">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <p className="font-bold">{entrega.numero_pedido}</p>
        <span
          className={`rounded-full border px-2 py-0.5 text-xs font-medium ${
            entrega.sin_senal ? 'border-aviso text-aviso' : 'border-exito text-exito'
          }`}
        >
          {entrega.sin_senal ? 'Sin señal' : 'En vivo'}
        </span>
      </div>
      <p className="text-sm">🛵 {entrega.repartidor ?? 'Sin repartidor'}</p>
      <p className="text-sm text-texto-suave">
        Va a {[entrega.destino_direccion, entrega.destino_barrio].filter(Boolean).join(', ') || 'dirección sin registrar'}
      </p>
      <p className="text-xs text-texto-suave">{textoUbicacion(entrega, ahora)}</p>
      {!entrega.destino && <p className="text-xs text-aviso">La dirección no tiene ubicación en el mapa.</p>}
    </li>
  )
}

// HU-38 · Pedidos "En camino" de la sede en un mapa, con cada repartidor donde está ahora.
// Se actualiza solo cada 30 segundos (el mismo ritmo con que los celulares envían la ubicación).
export default function MapaEntregas() {
  const [datos, setDatos] = useState(null)
  const [error, setError] = useState(null)
  const [actualizadoEn, setActualizadoEn] = useState(null)

  const cargar = useCallback(() => {
    obtenerMapaEnCamino()
      .then((respuesta) => {
        setDatos(respuesta)
        setError(null)
        setActualizadoEn(Date.now())
      })
      .catch((fallo) => setError(interpretarError(fallo).general))
  }, [])

  const intervalo = (datos?.intervalo_segundos ?? 30) * 1000

  useEffect(() => {
    cargar()
    const temporizador = setInterval(cargar, intervalo)
    return () => clearInterval(temporizador)
  }, [cargar, intervalo])

  return (
    <div className="flex flex-col gap-4">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold">Mapa de entregas</h1>
          <p className="text-texto-suave">
            Pedidos en camino de {datos?.sede?.nombre ?? 'la sede'}. Se actualiza solo cada {intervalo / 1000}{' '}
            segundos.
            {actualizadoEn &&
              ` Última actualización: ${new Date(actualizadoEn).toLocaleTimeString('es-CO', {
                hour: '2-digit',
                minute: '2-digit',
                second: '2-digit',
              })}`}
          </p>
        </div>
        <Boton variante="secundario" onClick={cargar}>
          Actualizar ahora
        </Boton>
      </header>

      {error && <Alerta tipo="error" titulo={error} />}
      {!datos && !error && <p className="text-texto-suave">Cargando el mapa…</p>}

      {datos && (
        <div className="grid gap-4 lg:grid-cols-[1fr_320px] [&>*]:min-w-0">
          <MapaEnCamino datos={datos} />
          <Tarjeta titulo={`En camino (${datos.entregas.length})`}>
            {datos.entregas.length === 0 ? (
              <p className="text-texto-suave">No hay pedidos en camino ahora mismo.</p>
            ) : (
              <ul className="flex flex-col gap-3">
                {datos.entregas.map((entrega) => (
                  <FilaEntrega key={entrega.pedido_id} entrega={entrega} ahora={actualizadoEn} />
                ))}
              </ul>
            )}
          </Tarjeta>
        </div>
      )}
    </div>
  )
}
