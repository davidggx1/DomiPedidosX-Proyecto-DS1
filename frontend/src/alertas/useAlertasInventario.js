import { useContext } from 'react'
import { AlertasInventarioContext } from './AlertasInventarioContext.js'

export function useAlertasInventario() {
  return useContext(AlertasInventarioContext)
}
