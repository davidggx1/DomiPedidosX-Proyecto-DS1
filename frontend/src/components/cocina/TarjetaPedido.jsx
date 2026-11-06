import { useState } from 'react'
import { obtenerComanda } from '../../api/cocina.js'
import { interpretarError } from '../../api/errores.js'
import { AVANCE_COCINA, textoTiempoEnCocina } from '../../utils/cocina.js'
import { horaCorta } from '../../utils/tiempo.js'
import Alerta from '../ui/Alerta.jsx'
import Boton from '../ui/Boton.jsx'
import DetalleComanda from './DetalleComanda.jsx'

// Card of the kitchen board. It expands to show the full order (HU-30)
// and has the button that moves the order to the next column (HU-31)
export default function TarjetaPedido({ tarjeta, ahora, ocupada, alAvanzar }) {
  const [abierta, setAbierta] = useState(false)
  const [comanda, setComanda] = useState(null)
  const [cargando, setCargando] = useState(false)
  const [error, setError] = useState(null)

  const avance = AVANCE_COCINA[tarjeta.estado]
  // the API tells which steps this role can give
  const puedeAvanzar = avance && tarjeta.siguientes_estados.includes(avance.estado)
  const idDetalle = `detalle-pedido-${tarjeta.id}`

  async function alternarDetalle() {
    const abrir = !abierta
    setAbierta(abrir)
    if (!abrir) return

    // always ask again when it opens, notes can change
    setCargando(true)
    setError(null)
    try {
      setComanda(await obtenerComanda(tarjeta.id))
    } catch (fallo) {
      setError(interpretarError(fallo).general)
    } finally {
      setCargando(false)
    }
  }

  return (
    <li className="flex flex-col gap-3 rounded-xl border border-borde bg-fondo p-3">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <p className="font-bold">{tarjeta.numero_pedido}</p>
          <p className="text-sm text-texto-suave">
            Llegó a las {horaCorta(tarjeta.recibido_en)} · {textoTiempoEnCocina(tarjeta, ahora)}
          </p>
        </div>
        <div className="flex flex-wrap gap-1">
          {tarjeta.tiene_notas && (
            <span className="rounded-full border border-aviso px-2 py-0.5 text-xs font-medium text-aviso">
              Con notas
            </span>
          )}
          {tarjeta.tiene_cambios && (
            <span className="rounded-full border border-borde px-2 py-0.5 text-xs font-medium">
              Con cambios
            </span>
          )}
        </div>
      </div>

      <ul className="flex flex-col gap-1 text-sm">
        {tarjeta.resumen.map((linea, indice) => (
          <li key={`${linea}-${indice}`}>{linea}</li>
        ))}
      </ul>

      {abierta && (
        <div id={idDetalle} className="border-t border-borde pt-3">
          {cargando && <p className="text-sm text-texto-suave">Cargando el detalle…</p>}
          {error && <Alerta tipo="error" titulo={error} />}
          {comanda && !cargando && <DetalleComanda comanda={comanda} />}
        </div>
      )}

      <div className="flex flex-wrap gap-2">
        <Boton
          variante="secundario"
          onClick={alternarDetalle}
          aria-expanded={abierta}
          aria-controls={idDetalle}
        >
          {abierta ? 'Ocultar detalle' : 'Ver detalle'}
        </Boton>
        {puedeAvanzar && (
          <Boton
            onClick={() => alAvanzar(tarjeta)}
            cargando={ocupada}
            aria-label={`${avance.texto}: pedido ${tarjeta.numero_pedido}`}
          >
            {avance.texto}
          </Boton>
        )}
      </div>
    </li>
  )
}
