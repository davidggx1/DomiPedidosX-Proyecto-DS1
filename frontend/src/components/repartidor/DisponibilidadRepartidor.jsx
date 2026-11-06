import { useEffect, useState } from 'react'
import { cambiarMiDisponibilidad, obtenerMiDisponibilidad } from '../../api/repartidores.js'
import { interpretarError } from '../../api/errores.js'
import Alerta from '../ui/Alerta.jsx'
import Interruptor from '../ui/Interruptor.jsx'

// Switch of the repartidor to say if he can receive orders (HU-41)
export default function DisponibilidadRepartidor() {
  const [disponible, setDisponible] = useState(null) // null while it loads
  const [guardando, setGuardando] = useState(false)
  const [error, setError] = useState(null)

  useEffect(() => {
    let vigente = true
    obtenerMiDisponibilidad()
      .then((datos) => {
        if (vigente) setDisponible(datos.disponible)
      })
      .catch((fallo) => {
        if (vigente) setError(interpretarError(fallo).general)
      })
    return () => {
      vigente = false
    }
  }, [])

  async function cambiar(nuevoValor) {
    setGuardando(true)
    setError(null)
    try {
      const datos = await cambiarMiDisponibilidad(nuevoValor)
      setDisponible(datos.disponible)
    } catch (fallo) {
      // the switch keeps its old value, so it never shows something the server did not save
      setError(interpretarError(fallo).general)
    } finally {
      setGuardando(false)
    }
  }

  return (
    <div className="flex flex-col gap-2 sm:items-end">
      <div className="flex items-center gap-3">
        <span
          className={`rounded-full border px-3 py-1 text-sm font-medium ${
            disponible ? 'border-exito text-exito' : 'border-borde text-texto-suave'
          }`}
        >
          {disponible === null ? 'Cargando…' : disponible ? 'Disponible' : 'No disponible'}
        </span>
        <Interruptor
          activo={Boolean(disponible)}
          alCambiar={cambiar}
          etiqueta="Estoy disponible para recibir pedidos"
          disabled={disponible === null}
          ocupado={guardando}
        />
      </div>
      {error && <Alerta tipo="error" titulo={error} />}
    </div>
  )
}
