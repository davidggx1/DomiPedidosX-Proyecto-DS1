// Geocodificación con Nominatim (OpenStreetMap), el mismo proveedor de los mapas.
// Su política de uso pide como máximo 1 petición por segundo: solo se llama
// cuando el usuario lo pide (botón "Buscar" o al soltar el pin), nunca al teclear.
const NOMINATIM = 'https://nominatim.openstreetmap.org'

// Centro y caja de Cali: los resultados de la ciudad salen primero.
export const CENTRO_CALI = [3.4516, -76.532]
const CAJA_CALI = '-76.62,3.55,-76.45,3.32'

const PARAMETROS_BASE = { format: 'jsonv2', 'accept-language': 'es', addressdetails: '1' }

async function consultar(ruta, parametros) {
  const url = `${NOMINATIM}/${ruta}?${new URLSearchParams({ ...PARAMETROS_BASE, ...parametros })}`
  const respuesta = await fetch(url, { headers: { Accept: 'application/json' } })
  if (!respuesta.ok) {
    throw new Error('El servicio de mapas no respondió. Inténtalo de nuevo en unos segundos.')
  }
  return respuesta.json()
}

function barrioDe(direccion = {}) {
  return direccion.neighbourhood ?? direccion.suburb ?? direccion.quarter ?? ''
}

// Busca coincidencias para un texto. Devuelve [{ id, nombre, latitud, longitud, barrio }].
export async function buscarDireccion(texto) {
  const resultados = await consultar('search', {
    q: texto,
    countrycodes: 'co',
    viewbox: CAJA_CALI,
    limit: '5',
  })
  return resultados.map((resultado) => ({
    id: resultado.place_id,
    nombre: resultado.display_name,
    latitud: Number(resultado.lat),
    longitud: Number(resultado.lon),
    barrio: barrioDe(resultado.address),
  }))
}

// Dirección aproximada de unas coordenadas, para sugerirla al mover el pin.
// Devuelve { texto, barrio } (vacíos si el mapa no los conoce) o null si no hay nada cerca.
// Sin calle no se arma texto: el nombre completo del lugar ("Golondrinas, Cali, Sur…")
// no le sirve al repartidor.
export async function direccionDesdeCoordenadas(latitud, longitud) {
  const resultado = await consultar('reverse', { lat: latitud, lon: longitud, zoom: '18' })
  if (!resultado || resultado.error) return null
  const { road, house_number: numero } = resultado.address ?? {}
  return {
    texto: road ? [road, numero].filter(Boolean).join(' # ') : '',
    barrio: barrioDe(resultado.address),
  }
}
