import { describe, expect, it } from 'vitest'
import { alertaDeEvento, aplicarEvento, avisoDeEvento, textoStock } from './alertasInventario.js'

const hamburguesa = {
  id: 1,
  tipo: 'producto',
  nombre: 'Hamburguesa',
  unidad: 'unidad',
  estado: 'activa',
  stock_actual: 3,
  stock_minimo: 5,
  creada_en: '2026-11-12T10:00:00Z',
}
const harina = {
  id: 2,
  tipo: 'insumo',
  nombre: 'Harina',
  unidad: 'kg',
  estado: 'activa',
  stock_actual: 2.5,
  stock_minimo: 3,
  creada_en: '2026-11-12T11:00:00Z',
}

describe('alertas de inventario mínimo (HU-16)', () => {
  it('solo reconoce los mensajes de alerta de inventario', () => {
    const datos = { tipo: 'alerta_inventario', transicion: 'creada', alerta: hamburguesa }
    expect(alertaDeEvento(datos)).toEqual({ transicion: 'creada', alerta: hamburguesa })
    expect(alertaDeEvento({ tipo: 'pedido_nuevo', pedido: {} })).toBeNull()
    expect(alertaDeEvento({ tipo: 'alerta_inventario' })).toBeNull()
    expect(alertaDeEvento(undefined)).toBeNull()
  })

  it('indica producto y stock actual contra el mínimo', () => {
    expect(textoStock(hamburguesa)).toBe('Quedan 3 unidades (mínimo 5)')
    expect(textoStock({ ...hamburguesa, stock_actual: 1 })).toBe('Quedan 1 unidad (mínimo 5)')
    expect(textoStock(harina)).toBe('Quedan 2,5 kg (mínimo 3 kg)')
  })

  it('un producto en cero aparece como agotado', () => {
    expect(textoStock({ ...hamburguesa, stock_actual: 0 })).toBe('Agotado (mínimo 5)')
  })

  it('una alerta nueva entra a la lista, la más reciente primero', () => {
    const lista = aplicarEvento([hamburguesa], { transicion: 'creada', alerta: harina })
    expect(lista.map((a) => a.id)).toEqual([2, 1])
  })

  it('no duplica la alerta mientras siga por debajo del mínimo', () => {
    const actualizada = { ...hamburguesa, stock_actual: 1 }
    const lista = aplicarEvento([hamburguesa, harina], { transicion: 'actualizada', alerta: actualizada })
    expect(lista).toHaveLength(2)
    expect(lista.find((a) => a.id === 1).stock_actual).toBe(1)
    const otra = aplicarEvento(lista, { transicion: 'creada', alerta: actualizada })
    expect(otra).toHaveLength(2)
  })

  it('se quita de la lista cuando se resuelve', () => {
    const resuelta = { ...hamburguesa, estado: 'resuelta' }
    const lista = aplicarEvento([hamburguesa, harina], { transicion: 'resuelta', alerta: resuelta })
    expect(lista.map((a) => a.id)).toEqual([2])
  })

  it('el aviso emergente solo sale con una alerta nueva', () => {
    const aviso = avisoDeEvento({ transicion: 'creada', alerta: hamburguesa })
    expect(aviso.titulo).toBe('Stock bajo: Hamburguesa')
    expect(aviso.texto).toBe('Quedan 3 unidades (mínimo 5)')
    expect(aviso.enlace).toBe('/operador/inventario')
    expect(avisoDeEvento({ transicion: 'actualizada', alerta: hamburguesa })).toBeNull()
    expect(avisoDeEvento({ transicion: 'resuelta', alerta: hamburguesa })).toBeNull()
  })

  it('el aviso de un producto en cero dice agotado', () => {
    const aviso = avisoDeEvento({ transicion: 'creada', alerta: { ...hamburguesa, stock_actual: 0 } })
    expect(aviso.titulo).toBe('Agotado: Hamburguesa')
  })
})
