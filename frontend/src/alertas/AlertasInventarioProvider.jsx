import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  conectarAlertasInventario,
  listarAgotadosPendientes,
  listarAlertasInventario,
} from '../api/inventario.js'
import AvisosInventario from '../components/inventario/AvisosInventario.jsx'
import {
  DURACION_AVISO_MS,
  alertaDeEvento,
  aplicarEvento,
  aplicarEventoAgotado,
  avisoDeAgotado,
  avisoDeCancelacionCocina,
  avisoDeEvento,
} from '../utils/alertasInventario.js'
import { AlertasInventarioContext } from './AlertasInventarioContext.js'

// HU-16 · Low stock alerts for the operator, on any of his screens (and HU-17 sold out reports, HU-33 kitchen errors).
// One socket keeps the list of active alerts live (the panel of Inventario reads
// it with useAlertasInventario) and a new alert also shows a popup
export default function AlertasInventarioProvider({ children }) {
  const [alertas, setAlertas] = useState([])
  const [agotados, setAgotados] = useState([]) // HU-17: pending sold out reports
  const [cargando, setCargando] = useState(true)
  const [avisos, setAvisos] = useState([])
  const navegar = useNavigate()

  useEffect(() => {
    let vigente = true
    const temporizadores = new Set()

    async function cargar() {
      const [alertasNuevas, agotadosNuevos] = await Promise.allSettled([
        listarAlertasInventario(),
        listarAgotadosPendientes(),
      ])
      if (!vigente) return
      // a failed request keeps what it had, the next event or reconnection fixes it
      if (alertasNuevas.status === 'fulfilled') setAlertas(alertasNuevas.value)
      if (agotadosNuevos.status === 'fulfilled') setAgotados(agotadosNuevos.value)
      setCargando(false)
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
        // HU-17: a sold out report arrived or was solved
        setAgotados((lista) => aplicarEventoAgotado(lista, datos))
        // HU-17: the kitchen reported a product as sold out
        // HU-33: the kitchen cancelled an order because of a kitchen error
        mostrar(avisoDeAgotado(datos) ?? avisoDeCancelacionCocina(datos))
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

  const valor = useMemo(
    () => ({ alertas, agotados, cargando, disponible: true }),
    [alertas, agotados, cargando],
  )

  return (
    <AlertasInventarioContext.Provider value={valor}>
      {children}
      <AvisosInventario avisos={avisos} alAbrir={abrir} alCerrar={cerrarAviso} />
    </AlertasInventarioContext.Provider>
  )
}
