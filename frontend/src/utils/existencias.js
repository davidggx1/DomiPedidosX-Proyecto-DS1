import { abreviaturaUnidad, formatearCantidad } from './unidades.js'

// How each kind of stock is shown and validated
export const TIPOS_EXISTENCIAS = {
  productos: {
    titulo: 'Productos',
    campoItem: 'producto',
    etiquetaItem: 'Producto',
    entero: true,
    paso: '1',
    nombre: (fila) => fila.producto_nombre,
  },
  insumos: {
    titulo: 'Ingredientes',
    campoItem: 'insumo',
    etiquetaItem: 'Ingrediente',
    entero: false,
    paso: '0.001',
    nombre: (fila) => fila.insumo_nombre,
  },
}

const CONTROL_STOCK = {
  PRODUCTO: 'Control por unidades',
  INSUMOS: 'Control por ingredientes',
  NINGUNO: 'Sin control de stock',
}

export function etiquetaControl(tipoControl) {
  return CONTROL_STOCK[tipoControl] ?? tipoControl
}

// Second line of a row: the category (and control) of a product, or the unit of an ingredient
export function detalleFila(tipo, fila) {
  if (tipo === 'productos') {
    return `${fila.categoria_nombre} · ${etiquetaControl(fila.tipo_control_stock)}`
  }
  return `Unidad: ${abreviaturaUnidad(fila.unidad_medida)}`
}

// 12 -> "12 und." for a product, "12.5 kg" for an ingredient
export function textoStock(tipo, fila, cantidad) {
  return tipo === 'productos'
    ? `${Number(cantidad)} und.`
    : formatearCantidad(cantidad, fila.unidad_medida)
}

// An empty stock hides the product from the menu only when it is controlled by units
export function estaAgotado(tipo, fila) {
  const sinStock = Number(fila.stock_actual) === 0
  return sinStock && (tipo === 'insumos' || fila.tipo_control_stock === 'PRODUCTO')
}
