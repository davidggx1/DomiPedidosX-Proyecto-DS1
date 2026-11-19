import { useId, useState } from 'react'
import { interpretarError } from '../../api/errores.js'
import { cancelarPedidoOperador } from '../../api/pedidos.js'
import { MOTIVOS_CANCELACION, MOTIVO_MAXIMO, armarMotivo, validarMotivo } from '../../utils/cancelacion.js'
import Alerta from '../ui/Alerta.jsx'
import Boton from '../ui/Boton.jsx'
import Modal from '../ui/Modal.jsx'
import Selector from '../ui/Selector.jsx'

// HU-34 · The operator cancels an order that was not delivered, with a reason.
// `alCerrar` must be stable (useCallback): Modal moves the focus when it changes
export default function ModalCancelarPedido({ pedido, alCerrar, alCancelar }) {
  const idForm = useId()
  const idDetalle = useId()
  const [codigo, setCodigo] = useState('')
  const [detalle, setDetalle] = useState('')
  const [errores, setErrores] = useState({})
  const [errorGeneral, setErrorGeneral] = useState(null)
  const [enviando, setEnviando] = useState(false)

  const detalleObligatorio = codigo === 'otro'

  async function enviar(evento) {
    evento.preventDefault()
    const problemas = validarMotivo(codigo, detalle)
    setErrores(problemas)
    if (Object.keys(problemas).length > 0) return

    setEnviando(true)
    setErrorGeneral(null)
    try {
      const cancelado = await cancelarPedidoOperador(pedido.id, armarMotivo(codigo, detalle))
      alCancelar(cancelado)
    } catch (error) {
      const { general, campos } = interpretarError(error)
      if (campos.motivo) setErrores({ detalle: campos.motivo })
      else setErrorGeneral(general)
      setEnviando(false)
    }
  }

  return (
    <Modal
      titulo={`Cancelar el pedido ${pedido.numero_pedido}`}
      alCerrar={alCerrar}
      acciones={
        <>
          <Boton variante="secundario" onClick={alCerrar} disabled={enviando}>
            Volver
          </Boton>
          <Boton variante="peligro" tipo="submit" form={idForm} cargando={enviando} disabled={!codigo}>
            Cancelar pedido
          </Boton>
        </>
      }
    >
      <form id={idForm} onSubmit={enviar} className="flex flex-col gap-3">
        <p className="text-sm text-texto-suave">
          Se devolverá el inventario, se liberará el cupo de cocina y de la promoción
          {pedido.repartidor ? `, y se le avisará a ${pedido.repartidor.nombre} que ya no debe entregarlo` : ''}.
          El cliente recibe el motivo.
        </p>
        {errorGeneral && <Alerta tipo="error" titulo={errorGeneral} />}

        <Selector
          etiqueta="Motivo"
          requerido
          opciones={MOTIVOS_CANCELACION}
          value={codigo}
          onChange={(e) => setCodigo(e.target.value)}
          error={errores.codigo}
          textoVacio="Selecciona el motivo"
        />

        <div className="flex flex-col gap-1">
          <label htmlFor={idDetalle} className="text-sm font-medium">
            {detalleObligatorio ? 'Describe el motivo' : 'Detalle (opcional)'}
            {detalleObligatorio && (
              <span className="text-marca-clara" aria-hidden="true">
                {' '}*
              </span>
            )}
          </label>
          <textarea
            id={idDetalle}
            value={detalle}
            onChange={(e) => setDetalle(e.target.value)}
            maxLength={MOTIVO_MAXIMO}
            rows={3}
            aria-required={detalleObligatorio || undefined}
            aria-invalid={errores.detalle ? true : undefined}
            aria-describedby={errores.detalle ? `${idDetalle}-error` : undefined}
            placeholder="Ej: el cliente llamó para cambiar la dirección"
            className={`w-full rounded-xl border bg-fondo px-3 py-2 text-texto placeholder:text-texto-suave ${
              errores.detalle ? 'border-error' : 'border-borde'
            }`}
          />
          {errores.detalle && (
            <p id={`${idDetalle}-error`} className="text-sm text-error">
              {errores.detalle}
            </p>
          )}
        </div>
      </form>
    </Modal>
  )
}
