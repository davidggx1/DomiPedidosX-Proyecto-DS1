import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { conectarMisEntregas } from '../../api/repartidores.js'
import { avisoDeMensaje, duracionAviso } from '../../utils/avisos.js'
import { prepararSonido, sonarAviso } from '../../utils/sonido.js'

const ESTILO = {
  asignado: 'border-exito',
  retirado: 'border-aviso',
}

// HU-40 · Avisos en tiempo real para el repartidor, en cualquier pantalla de la app.
// Escucha el mismo WebSocket de su lista (HU-42); cuando el mensaje trae un aviso,
// suena y muestra una tarjeta. Tocar un aviso de asignación abre el detalle del pedido.
export default function AvisosRepartidor() {
  const [avisos, setAvisos] = useState([])
  const navegar = useNavigate()

  useEffect(() => prepararSonido(), [])

  useEffect(() => {
    const temporizadores = new Set()

    function quitar(id) {
      setAvisos((lista) => lista.filter((aviso) => aviso.id !== id))
    }

    const cerrar = conectarMisEntregas({
      alMensaje: (datos) => {
        const aviso = avisoDeMensaje(datos)
        if (!aviso) return
        sonarAviso()
        setAvisos((lista) => [...lista, aviso])
        const temporizador = setTimeout(() => {
          temporizadores.delete(temporizador)
          quitar(aviso.id)
        }, duracionAviso(aviso))
        temporizadores.add(temporizador)
      },
    })

    return () => {
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

  if (avisos.length === 0) return null

  return (
    <div
      aria-live="assertive"
      className="fixed inset-x-0 top-2 z-50 mx-auto flex w-full max-w-md flex-col gap-2 px-4"
    >
      {avisos.map((aviso) => (
        <div
          key={aviso.id}
          role="alert"
          className={`flex items-start gap-3 rounded-xl border-2 bg-superficie p-4 shadow-lg ${ESTILO[aviso.tipo]}`}
        >
          <div className="flex-1">
            <p className="font-bold">{aviso.titulo}</p>
            <p className="text-sm text-texto-suave">{aviso.texto}</p>
            {aviso.enlace && (
              <button
                type="button"
                onClick={() => abrir(aviso)}
                className="mt-2 min-h-11 rounded-lg bg-marca px-4 py-2 font-medium text-white hover:bg-marca-oscura"
              >
                Ver pedido y dirección
              </button>
            )}
          </div>
          <button
            type="button"
            onClick={() => cerrarAviso(aviso.id)}
            aria-label="Cerrar aviso"
            className="min-h-11 min-w-11 rounded-lg text-texto-suave hover:bg-superficie-alta"
          >
            ✕
          </button>
        </div>
      ))}
    </div>
  )
}
