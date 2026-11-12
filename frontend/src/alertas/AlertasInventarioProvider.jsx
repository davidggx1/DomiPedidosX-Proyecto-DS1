import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { conectarAlertasInventario, listarAlertasInventario } from '../api/inventario.js'
import AvisosInventario from '../components/inventario/AvisosInventario.jsx'
import {
  DURACION_AVISO_MS,
  alertaDeEvento,
  aplicarEvento,
  avisoDeEvento,
} from '../utils/alertasInventario.js'
import { AlertasInventarioContext } from './AlertasInventarioContext.js'

// HU-16 · Low stock alerts for the operator, on any of his screens.
// One socket keeps the list of active alerts live (the panel of Inventario reads
// it with useAlertasInventario) and a new alert also shows a popup
export default function AlertasInventarioProvider({ children }) {
  const [alertas, setAlertas] = useState([])
  const [cargando, setCargando] = useState(true)
  const [avisos, setAvisos] = useState([])
  const navegar = useNavigate()

  useEffect(() => {
    let vigente = true
    const temporizadores = new Set()

    async function cargar() {
      try {
        const datos = await listarAlertasInventario()
        if (vigente) setAlertas(datos)
      } catch {
        // the panel keeps what it had, the next event or reconnection fixes it
      } finally {
        if (vigente) setCargando(false)
      }
    }
    cargar()

    const cerrar = conectarAlertasInventario({
      // events sent while the socket was down were lost
      alReconectar: cargar,
      alMensaje: (datos) => {
        const evento = alertaDeEvento(datos)
        if (!evento) return
        setAlertas((lista) => aplicarEvento(lista, evento))

        const aviso = avisoDeEvento(evento)
        if (!aviso) return
        setAvisos((lista) => [...lista.filter((actual) => actual.id !== aviso.id), aviso])
        const temporizador = setTimeout(() => {
          temporizadores.delete(temporizador)
          setAvisos((lista) => lista.filter((actual) => actual.id !== aviso.id))
        }, DURACION_AVISO_MS)
        temporizadores.add(temporizador)
      },
    })

    return () => {
      vigente = false
      cerrar()
      temporizadores.forEach(clearTimeout)
    }
  }, [])

  function cerrarAviso(id) {
    setAvisos((lista) => lista.filter((aviso) => aviso.id !== id))
  }

  function abrir(aviso) {
    cerrarAviso(aviso.id)
    navegar(aviso.enlace)
  }

  const valor = useMemo(() => ({ alertas, cargando, disponible: true }), [alertas, cargando])

  return (
    <AlertasInventarioContext.Provider value={valor}>
      {children}
      <AvisosInventario avisos={avisos} alAbrir={abrir} alCerrar={cerrarAviso} />
    </AlertasInventarioContext.Provider>
  )
}
