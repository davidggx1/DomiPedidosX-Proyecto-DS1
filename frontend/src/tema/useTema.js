import { useCallback, useEffect, useState } from 'react'
import {
  TEMAS,
  aplicarTema,
  esTemaValido,
  guardarTema,
  leerTemaGuardado,
  resolverTema,
  sistemaPrefiereOscuro,
  temaContrario,
} from './tema.js'

// Tema activo y función para cambiarlo.
// index.html ya aplicó el tema antes de que cargue React (sin parpadeo),
// así que el estado inicial se lee del documento.
export function useTema() {
  const [tema, setTema] = useState(() => {
    const actual = document.documentElement.dataset.tema
    return esTemaValido(actual) ? actual : resolverTema(leerTemaGuardado(), sistemaPrefiereOscuro())
  })

  useEffect(() => {
    aplicarTema(tema)
  }, [tema])

  // Mientras la persona no haya elegido, sigue los cambios del sistema.
  useEffect(() => {
    const consulta = window.matchMedia?.('(prefers-color-scheme: dark)')
    if (!consulta) return undefined
    const alCambiar = (evento) => {
      if (!esTemaValido(leerTemaGuardado())) setTema(evento.matches ? TEMAS.OSCURO : TEMAS.CLARO)
    }
    consulta.addEventListener('change', alCambiar)
    return () => consulta.removeEventListener('change', alCambiar)
  }, [])

  const alternarTema = useCallback(() => {
    setTema((anterior) => {
      const siguiente = temaContrario(anterior)
      guardarTema(siguiente)
      return siguiente
    })
  }, [])

  return { tema, alternarTema }
}
