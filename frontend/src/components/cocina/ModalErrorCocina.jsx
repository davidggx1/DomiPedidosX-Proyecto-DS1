import { useId, useState } from 'react'
import { cancelarPorErrorCocina } from '../../api/cocina.js'
import { interpretarError } from '../../api/errores.js'
import { JUSTIFICACION_MAXIMA, validarJustificacion } from '../../utils/cocina.js'
import Alerta from '../ui/Alerta.jsx'
import Boton from '../ui/Boton.jsx'
import Modal from '../ui/Modal.jsx'

// HU-33 · The kitchen cancels an order because of a kitchen error.
// The justification is required: the customer and the operator receive it.
// `alCerrar` must be stable (useCallback): Modal moves the focus when it changes
export default function ModalErrorCocina({ tarjeta, alCerrar, alCancelar }) {
  const idCampo = useId()
  const [justificacion, setJustificacion] = useState('')
  const [enviando, setEnviando] = useState(false)
  const [errorCampo, setErrorCampo] = useState(null)
  const [errorGeneral, setErrorGeneral] = useState(null)

  async function enviar(evento) {
    evento.preventDefault()
    const problema = validarJustificacion(justificacion)
    if (problema) {
      setErrorCampo(problema)
      return
    }
    setEnviando(true)
    setErrorCampo(null)
    setErrorGeneral(null)
    try {
      const pedido = await cancelarPorErrorCocina(tarjeta.id, justificacion.trim())
      alCancelar(pedido)
    } catch (error) {
      const { general, campos } = interpretarError(error)
      if (campos.justificacion) setErrorCampo(campos.justificacion)
      else setErrorGeneral(general)
      setEnviando(false)
    }
  }

  return (
    <Modal
      titulo={`Cancelar ${tarjeta.numero_pedido} por error de cocina`}
      alCerrar={alCerrar}
      acciones={
        <>
          <Boton variante="secundario" onClick={alCerrar} disabled={enviando}>
            Volver
          </Boton>
          <Boton
            variante="peligro"
            tipo="submit"
            form={`${idCampo}-form`}
            cargando={enviando}
            disabled={!justificacion.trim()}
          >
            Cancelar pedido
          </Boton>
        </>
      }
    >
      <form id={`${idCampo}-form`} onSubmit={enviar} className="flex flex-col gap-3">
        <p className="text-sm text-texto-suave">
          El pedido quedará cancelado, se devolverá el inventario y se avisará al cliente y al operador con esta
          justificación.
        </p>
        {errorGeneral && <Alerta tipo="error" titulo={errorGeneral} />}
        <div className="flex flex-col gap-1">
          <label htmlFor={idCampo} className="text-sm font-medium">
            Justificación del error
            <span className="text-marca-clara" aria-hidden="true">
              {' '}*
            </span>
          </label>
          <textarea
            id={idCampo}
            value={justificacion}
            onChange={(e) => setJustificacion(e.target.value)}
            maxLength={JUSTIFICACION_MAXIMA}
            rows={4}
            required
            aria-required="true"
            aria-invalid={errorCampo ? true : undefined}
            aria-describedby={errorCampo ? `${idCampo}-error` : `${idCampo}-ayuda`}
            placeholder="Ej: se quemó la carne y no hay más para repetir el plato"
            className={`w-full rounded-xl border bg-fondo px-3 py-2 text-texto placeholder:text-texto-suave ${
              errorCampo ? 'border-error' : 'border-borde'
            }`}
          />
          {errorCampo ? (
            <p id={`${idCampo}-error`} className="text-sm text-error">
              {errorCampo}
            </p>
          ) : (
            <p id={`${idCampo}-ayuda`} className="text-sm text-texto-suave">
              {justificacion.trim().length}/{JUSTIFICACION_MAXIMA} caracteres
            </p>
          )}
        </div>
      </form>
    </Modal>
  )
}
