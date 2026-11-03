// Unidades de medida de los ingredientes (mismos valores que Insumo.UnidadMedida en Django).
export const UNIDADES = [
  { valor: 'unidad', etiqueta: 'Unidades' },
  { valor: 'g', etiqueta: 'Gramos (g)' },
  { valor: 'kg', etiqueta: 'Kilogramos (kg)' },
  { valor: 'ml', etiqueta: 'Mililitros (ml)' },
  { valor: 'l', etiqueta: 'Litros (l)' },
]

const ABREVIATURA = { unidad: 'und.', g: 'g', kg: 'kg', ml: 'ml', l: 'l' }

// 'g' -> "g", 'unidad' -> "und."
export function abreviaturaUnidad(unidad) {
  return ABREVIATURA[unidad] ?? unidad
}

// 10 + 'g' -> "10 g". Quita ceros sobrantes de los decimales ("10.000" -> "10").
export function formatearCantidad(cantidad, unidad) {
  return `${Number(cantidad)} ${abreviaturaUnidad(unidad)}`
}
