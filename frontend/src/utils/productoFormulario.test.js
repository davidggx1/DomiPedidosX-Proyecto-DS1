import { describe, expect, it } from 'vitest'
import { armarDatosProducto } from './productoFormulario.js'
import {
  CONTROL_POR_DEFECTO,
  OPCIONES_CONTROL_STOCK,
  ayudaControlStock,
  controlStockInicial,
} from './controlStock.js'

const valores = {
  nombre: ' Clásica ',
  descripcion: '',
  precio_base: '15000',
  tiempo_preparacion: '10',
  categoria: '2',
  sedes: ['1', '3'],
  activo: true,
  tipo_control_stock: 'PRODUCTO',
}

describe('tipo de control de stock en el formulario de productos (HU-14)', () => {
  it('las opciones son los tres valores del servidor, con su ayuda', () => {
    expect(OPCIONES_CONTROL_STOCK.map((opcion) => opcion.valor)).toEqual([
      'PRODUCTO',
      'INSUMOS',
      'NINGUNO',
    ])
    expect(OPCIONES_CONTROL_STOCK.map((opcion) => opcion.etiqueta)).toEqual([
      'Producto terminado',
      'Por insumos',
      'Sin control',
    ])
    OPCIONES_CONTROL_STOCK.forEach((opcion) => expect(opcion.ayuda.length).toBeGreaterThan(10))
  })

  it('la ayuda cambia con la opción elegida', () => {
    expect(ayudaControlStock('NINGUNO')).toBe('No se descuenta ni se bloquea por stock.')
    expect(ayudaControlStock('PRODUCTO')).toContain('con stock 0 no se puede comprar')
    expect(ayudaControlStock('INSUMOS')).toContain('ingredientes de su receta')
    expect(ayudaControlStock('otro')).toBe('')
  })

  it('al crear parte de "Sin control"', () => {
    expect(CONTROL_POR_DEFECTO).toBe('NINGUNO')
    expect(controlStockInicial(null)).toBe('NINGUNO')
    expect(controlStockInicial(undefined)).toBe('NINGUNO')
  })

  it('al editar muestra el valor actual del producto', () => {
    expect(controlStockInicial({ tipo_control_stock: 'INSUMOS' })).toBe('INSUMOS')
    expect(controlStockInicial({ tipo_control_stock: 'PRODUCTO' })).toBe('PRODUCTO')
  })

  it('un producto sin el campo (respuesta antigua) se muestra como "Sin control"', () => {
    expect(controlStockInicial({ nombre: 'Antiguo' })).toBe('NINGUNO')
    expect(controlStockInicial({ tipo_control_stock: '' })).toBe('NINGUNO')
  })

  it('al crear envía el tipo elegido', () => {
    for (const tipo of ['PRODUCTO', 'INSUMOS', 'NINGUNO']) {
      const datos = armarDatosProducto({
        valores: { ...valores, tipo_control_stock: tipo },
        archivo: null,
        producto: null,
      })
      expect(datos.get('tipo_control_stock')).toBe(tipo)
    }
  })

  it('al editar envía el tipo elegido, aunque no cambien las sedes', () => {
    const producto = { id: 5, sedes: [1, 3], tipo_control_stock: 'NINGUNO' }
    const datos = armarDatosProducto({
      valores: { ...valores, tipo_control_stock: 'INSUMOS' },
      archivo: null,
      producto,
    })
    expect(datos.get('tipo_control_stock')).toBe('INSUMOS')
    expect(datos.get('activo')).toBe('true')
    expect(datos.getAll('sedes')).toEqual([])
  })

  it('sigue enviando lo demás como antes', () => {
    const datos = armarDatosProducto({ valores, archivo: null, producto: null })
    expect(datos.get('nombre')).toBe('Clásica')
    expect(datos.get('precio_base')).toBe('15000')
    expect(datos.get('categoria')).toBe('2')
    expect(datos.getAll('sedes')).toEqual(['1', '3'])
    expect(datos.get('activo')).toBeNull()
  })

  it('al editar con otras sedes las envía', () => {
    const producto = { id: 5, sedes: [1], tipo_control_stock: 'NINGUNO' }
    const datos = armarDatosProducto({ valores, archivo: null, producto })
    expect(datos.getAll('sedes')).toEqual(['1', '3'])
  })
})
