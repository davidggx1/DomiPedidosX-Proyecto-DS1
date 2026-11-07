import { useEffect, useState } from 'react'
import { cambiarDisponibilidad, obtenerDisponibilidad } from '../../api/menu.js'
import { interpretarError } from '../../api/errores.js'
import Alerta from '../ui/Alerta.jsx'
import Interruptor from '../ui/Interruptor.jsx'

// HU-13 · Interruptores de disponibilidad de un producto, uno por sede.
// Cada cambio afecta solo a su sede; las que el operador no gestiona se ven bloqueadas.
export default function DisponibilidadProducto({ producto, alCambiar }) {
  const [estado, setEstado] = useState(null)
  const [error, setError] = useState(null)
  const [sedeOcupada, setSedeOcupada] = useState(null)

  useEffect(() => {
    let vigente = true
    obtenerDisponibilidad(producto.id)
      .then((datos) => {
        if (vigente) setEstado(datos)
      })
      .catch((err) => {
        if (vigente) setError(interpretarError(err).general)
      })
    return () => {
      vigente = false
    }
  }, [producto.id])

  async function cambiar(fila, disponible) {
    setSedeOcupada(fila.sede)
    setError(null)
    try {
      setEstado(await cambiarDisponibilidad(producto.id, fila.sede, disponible))
      alCambiar?.()
    } catch (err) {
      setError(interpretarError(err).general)
    } finally {
      setSedeOcupada(null)
    }
  }

  return (
    <div className="flex flex-col gap-2 border-t border-borde pt-3">
      <p className="text-sm font-medium">Disponibilidad por sede</p>
      {error && <Alerta tipo="error" titulo={error} />}
      {!estado && !error && <p className="text-sm text-texto-suave">Cargando…</p>}
      {estado?.length === 0 && (
        <p className="text-sm text-texto-suave">No hay sedes activas.</p>
      )}
      {estado?.length > 0 && (
        <ul className="flex flex-col">
          {estado.map((fila) => (
            <li key={fila.sede} className="flex items-center justify-between gap-3">
              <span className="flex flex-col">
                <span>{fila.sede_nombre}</span>
                <span className={`text-xs ${fila.disponible ? 'text-exito' : 'text-aviso'}`}>
                  {fila.disponible ? 'Disponible' : 'No disponible'}
                  {!fila.editable && ' · no es tu sede'}
                </span>
              </span>
              <Interruptor
                activo={fila.disponible}
                alCambiar={(valor) => cambiar(fila, valor)}
                etiqueta={`${producto.nombre} disponible en ${fila.sede_nombre}`}
                disabled={!fila.editable}
                ocupado={sedeOcupada === fila.sede}
              />
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
