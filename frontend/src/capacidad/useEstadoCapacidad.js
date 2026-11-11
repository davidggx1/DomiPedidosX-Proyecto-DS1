import { useCallback, useEffect, useState } from 'react'
import { obtenerEstadoCapacidad } from '../api/capacidades.js'

const CADA_MS = 15000

// Capacity of a sede (HU-61), asked again every few seconds so the button
// reacts when a slot is released. Customers pass the sede id, the operator
// passes nothing and gets his own sede
export function useEstadoCapacidad({ sedeId, activo = true, cadaMs = CADA_MS } = {}) {
  const [estado, setEstado] = useState(null)
  const [consulta, setConsulta] = useState(0)

  // asks again right now (after sending an order, for example)
  const refrescar = useCallback(() => setConsulta((n) => n + 1), [])

  useEffect(() => {
    if (!activo) return undefined
    let vigente = true

    const consultar = async () => {
      try {
        const datos = await obtenerEstadoCapacidad(sedeId)
        if (vigente) setEstado(datos)
      } catch {
        // unknown state, the backend still blocks when the order is sent
        if (vigente) setEstado(null)
      }
    }

    consultar()
    const temporizador = setInterval(consultar, cadaMs)
    return () => {
      vigente = false
      clearInterval(temporizador)
    }
  }, [activo, sedeId, cadaMs, consulta])

  return { estado, refrescar }
}
