import { createContext } from 'react'

// Active low stock alerts of the sede (HU-16) and pending sold out reports of
// the kitchen (HU-17). Outside the provider (any role that is not operator)
// the lists are empty and `disponible` is false
export const AlertasInventarioContext = createContext({
  alertas: [],
  agotados: [],
  cargando: false,
  disponible: false,
})
