import { useEffect, useRef, useState } from 'react'
import { interpretarError } from '../../api/errores.js'
import { actualizarEntrega } from '../../api/repartidores.js'
import { calcularCambio } from '../../utils/entregas.js'
import { formatearPrecio } from '../../utils/formato.js'
import Alerta from '../ui/Alerta.jsx'
import Boton from '../ui/Boton.jsx'
import CampoTexto from '../ui/CampoTexto.jsx'

// Asks the repartidor to confirm each step of the delivery (HU-45).
// When he delivers an order paid in cash, he also writes how much money he received
export default function ConfirmarPasoEntrega({ entrega, avance, alCerrar, alConfirmar }) {
  const dialogo = useRef(null)
  const [monto, setMonto] = useState('')
  const [enviando, setEnviando] = useState(false)
  const [error, setError] = useState(null)

  const pideMonto = avance.estado === 'entregado' && entrega.cobrar_en_efectivo
  const cambio = pideMonto ? calcularCambio(monto, entrega.total) : null
  const montoInsuficiente = pideMonto && monto !== '' && cambio === null

  useEffect(() => {
    dialogo.current?.showModal()
  }, [])

  async function confirmar(evento) {
    evento.preventDefault()
    setEnviando(true)
    setError(null)
    try {
      const datos = await actualizarEntrega(entrega.id, avance.estado, pideMonto ? monto : null)
      alConfirmar(datos)
    } catch (fallo) {
      const { general, campos } = interpretarError(fallo)
      setError(campos.monto_recaudado ?? general)
      setEnviando(false)
    }
  }

  return (
    <dialog
      ref={dialogo}
      onClose={alCerrar}
      aria-labelledby="titulo-paso-entrega"
      className="m-auto w-[calc(100%-2rem)] max-w-md rounded-xl border border-borde bg-superficie p-0 text-texto backdrop:bg-black/50"
    >
      <form onSubmit={confirmar} className="flex flex-col gap-4 p-4">
        <h2 id="titulo-paso-entrega" className="text-xl font-bold">
          {avance.texto}
        </h2>
        <p>
          {avance.pregunta} <span className="text-texto-suave">Pedido {entrega.numero_pedido}.</span>
        </p>

        {pideMonto && (
          <div className="flex flex-col gap-2">
            <p className="font-semibold text-aviso">Total a cobrar: {formatearPrecio(entrega.total)}</p>
            <CampoTexto
              etiqueta="Dinero recibido del cliente"
              type="number"
              inputMode="numeric"
              min={entrega.total}
              step="50"
              requerido
              required
              autoFocus
              value={monto}
              onChange={(evento) => setMonto(evento.target.value)}
              error={montoInsuficiente ? 'El monto no alcanza para el total del pedido.' : undefined}
            />
            {cambio !== null && (
              <p className="text-lg">
                Cambio para el cliente: <strong>{formatearPrecio(cambio)}</strong>
              </p>
            )}
          </div>
        )}

        {error && <Alerta tipo="error" titulo={error} />}

        <div className="flex flex-wrap justify-end gap-2">
          <Boton variante="secundario" onClick={() => dialogo.current?.close()} disabled={enviando}>
            Cancelar
          </Boton>
          <Boton tipo="submit" cargando={enviando} disabled={pideMonto && cambio === null}>
            Sí, confirmar
          </Boton>
        </div>
      </form>
    </dialog>
  )
}
