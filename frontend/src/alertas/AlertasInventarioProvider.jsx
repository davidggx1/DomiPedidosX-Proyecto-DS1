import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { conectarAlertasInventario, listarAlertasInventario } from '../api/inventario.js'
import AvisosInventario from '../components/inventario/AvisosInventario.jsx'
import {
  DURACION_AVISO_MS,
  alertaDeEvento,
  aplicarEvento,
  avisoDeAgotado,
  avisoDeEvento,
} from '../utils/alertasInventario.js'
import { AlertasInventarioContext } from './AlertasInventarioContext.js'

// HU-16 · Low stock alerts for the operator, on any of his screens (and HU-17 sold out reports).
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

    // shows a popup that closes by itself after a while
    function mostrar(aviso) {
      if (!aviso) return
      setAvisos((lista) => [...lista.filter((actual) => actual.id !== aviso.id), aviso])
      const temporizador = setTimeout(() => {
        temporizadores.delete(temporizador)
        setAvisos((lista) => lista.filter((actual) => actual.id !== aviso.id))
      }, DURACION_AVISO_MS)
      temporizadores.add(temporizador)
    }

    const cerrar = conectarAlertasInventario({
      // events sent while the socket was down were lost
      alReconectar: cargar,
      alMensaje: (datos) => {
        const evento = alertaDeEvento(datos)
        if (evento) {
          setAlertas((lista) => aplicarEvento(lista, evento))
          mostrar(avisoDeEvento(evento))
          return
        }
        // HU-17: the kitchen reported a product as sold out
        mostrar(avisoDeAgotado(datos))
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
