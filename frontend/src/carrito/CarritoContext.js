import { createContext } from 'react'

// Contexto con las líneas del carrito y sus acciones (HU-21).
// Se consume con el hook useCarrito().
export const CarritoContext = createContext(null)
