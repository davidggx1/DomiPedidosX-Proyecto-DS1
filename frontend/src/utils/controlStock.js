// HU-11 / HU-14 · Stock control type of a product

export const CONTROL_POR_DEFECTO = 'NINGUNO'

// Same values the backend accepts (Producto.TipoControlStock)
export const OPCIONES_CONTROL_STOCK = [
  {
    valor: 'PRODUCTO',
    etiqueta: 'Producto terminado',
    ayuda:
      'Se controla con la existencia del propio producto en cada sede y cada pedido la descuenta. Registra su stock en Inventario: con stock 0 no se puede comprar.',
  },
  {
    valor: 'INSUMOS',
    etiqueta: 'Por insumos',
    ayuda:
      'Se controla con los ingredientes de su receta y su existencia en cada sede. Si le falta alguno, no se puede comprar.',
  },
  {
    valor: 'NINGUNO',
    etiqueta: 'Sin control',
    ayuda: 'No se descuenta ni se bloquea por stock.',
  },
]

export function ayudaControlStock(valor) {
  return OPCIONES_CONTROL_STOCK.find((opcion) => opcion.valor === valor)?.ayuda ?? ''
}

// What the selector shows when the form opens: the current value of the product when
// editing (products that never had one come as "Sin control"), the default when creating
export function controlStockInicial(producto) {
  return producto?.tipo_control_stock || CONTROL_POR_DEFECTO
}
