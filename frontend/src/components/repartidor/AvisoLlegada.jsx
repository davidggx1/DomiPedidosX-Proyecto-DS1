import { useState } from 'react'
import { interpretarError } from '../../api/errores.js'
import { avisarLlegada } from '../../api/repartidores.js'
import { horaCorta } from '../../utils/tiempo.js'
import Alerta from '../ui/Alerta.jsx'
import Boton from '../ui/Boton.jsx'

// HU-39 · Before picking up, the courier tells the kitchen he is at the branch.
// Only while the order is "listo para despacho"; afterwards it shows when he did it.
export default function AvisoLlegada({ entrega, alAvisar }) {
  const [enviando, setEnviando] = useState(false)
  const [error, setError] = useState(null)

  if (entrega.estado !== 'listo_despacho') return null

  if (entrega.repartidor_llego_en) {
    return (
      <p role="status" className="rounded-xl border border-exito bg-exito/15 px-4 py-3 text-exito">
        A las {horaCorta(entrega.repartidor_llego_en)} avisaste tu llegada: cocina ya sabe que estás en la sede.
      </p>
    )
  }

  async function avisar() {
    setEnviando(true)
    setError(null)
    try {
      alAvisar(await avisarLlegada(entrega.id))
    } catch (fallo) {
      setError(interpretarError(fallo).general)
    } finally {
      setEnviando(false)
    }
  }

  return (
    <div className="flex flex-col gap-2">
      {error && <Alerta tipo="error" titulo={error} />}
      <Boton variante="secundario" cargando={enviando} onClick={avisar} className="w-full text-lg">
        Llegué a la sede
      </Boton>
    </div>
  )
}
