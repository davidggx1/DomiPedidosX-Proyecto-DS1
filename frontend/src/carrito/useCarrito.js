import { useContext } from 'react'
import { CarritoContext } from './CarritoContext.js'

export function useCarrito() {
  const contexto = useContext(CarritoContext)
  if (!contexto) {
    throw new Error('useCarrito debe usarse dentro de <CarritoProvider>.')
  }
  return contexto
}
