import { createContext } from 'react'

// Active low stock alerts of the sede (HU-16). Outside the provider (any role
// that is not operator) the list is empty and `disponible` is false
export const AlertasInventarioContext = createContext({
  alertas: [],
  cargando: false,
  disponible: false,
})
