// HU-38 · Ubicación de los repartidores en camino.

// Estados en los que el repartidor lleva el pedido y su celular comparte la ubicación
export const ESTADOS_RASTREO = ['recogido', 'en_camino']
export const INTERVALO_UBICACION_MS = 30000

export function llevaPedido(entregas) {
  return (entregas ?? []).some((entrega) => ESTADOS_RASTREO.includes(entrega.estado))
}

function haceCuanto(segundos) {
  if (segundos < 60) return `hace ${Math.max(0, Math.round(segundos))} s`
  const minutos = Math.floor(segundos / 60)
  return `hace ${minutos} min`
}

// Texto bajo cada pedido del mapa del operador
export function textoUbicacion(entrega, ahora = Date.now()) {
  if (!entrega.ubicacion_actualizada_en) return 'Aún sin ubicación del repartidor'
  const segundos = (ahora - Date.parse(entrega.ubicacion_actualizada_en)) / 1000
  return entrega.sin_senal ? `Sin señal desde ${haceCuanto(segundos)}` : `Ubicación de ${haceCuanto(segundos)}`
}

// Puntos que el mapa debe encuadrar: la sede, los repartidores y los destinos
export function puntosDelMapa(datos) {
  const puntos = []
  const agregar = (punto) => punto && puntos.push([punto.latitud, punto.longitud])
  agregar(datos?.sede?.ubicacion)
  for (const entrega of datos?.entregas ?? []) {
    agregar(entrega.ubicacion)
    agregar(entrega.destino)
  }
  return puntos
}

// HU-49 · Texto que ve el cliente bajo el mapa de su pedido
export function textoUbicacionCliente(datos, ahora = Date.now()) {
  const quien = datos?.repartidor ?? 'El repartidor'
  if (!datos?.ubicacion_actualizada_en) return `${quien} ya salió con tu pedido. Esperando su ubicación…`
  const segundos = (ahora - Date.parse(datos.ubicacion_actualizada_en)) / 1000
  if (datos.sin_senal) {
    const de = datos.repartidor ? `de ${datos.repartidor}` : 'del repartidor'
    return `Perdimos la señal ${de} ${haceCuanto(segundos)}. Tu pedido sigue en camino.`
  }
  return `${quien} va en camino · ubicación de ${haceCuanto(segundos)}`
}
