import Alerta from '../ui/Alerta.jsx'
import Boton from '../ui/Boton.jsx'
import Modal from '../ui/Modal.jsx'
import { formatearPrecio } from '../../utils/formato.js'
import { textoDistancia, textoNoDisponibles } from '../../utils/alternativas.js'

// HU-62 · What the customer can do when his sede cannot take the order now:
// order from another sede close to him, or wait for the next slot of his sede
export default function ModalAlternativas({ datos, cargando, error, alElegir, alCerrar }) {
  const alternativas = datos?.alternativas ?? []
  const siguiente = datos?.siguiente_franja

  return (
    <Modal
      titulo="Tu sede no puede recibir el pedido ahora"
      alCerrar={alCerrar}
      acciones={
        <Boton variante="secundario" onClick={alCerrar}>
          Cerrar
        </Boton>
      }
    >
      {cargando && <p>Buscando alternativas cerca de ti…</p>}
      {error && <Alerta tipo="error" titulo={error} />}

      {datos && alternativas.length > 0 && (
        <>
          <p>Estas sedes cubren tu dirección y tienen cupo ahora mismo:</p>
          <ul className="mt-3 flex flex-col gap-3">
            {alternativas.map((alternativa) => {
              const faltantes = textoNoDisponibles(alternativa)
              return (
                <li key={alternativa.sede.id} className="rounded-lg border border-borde p-3">
                  <p className="font-semibold">{alternativa.sede.nombre}</p>
                  <p className="text-sm text-texto-suave">{alternativa.sede.direccion}</p>
                  <p className="mt-1 text-sm">
                    A {textoDistancia(alternativa.distancia_km)} · Entrega en{' '}
                    {alternativa.tiempo_estimado} min · Domicilio{' '}
                    {formatearPrecio(alternativa.tarifa_domicilio)} · Pedido mínimo{' '}
                    {formatearPrecio(alternativa.pedido_minimo)}
                  </p>
                  {faltantes && <p className="mt-1 text-sm text-aviso">{faltantes}</p>}
                  <Boton
                    variante="primario"
                    className="mt-2"
                    onClick={() => alElegir(alternativa)}
                    aria-label={`Cambiar a la sede ${alternativa.sede.nombre}`}
                  >
                    Cambiar a esta sede
                  </Boton>
                </li>
              )
            })}
          </ul>
        </>
      )}

      {datos && alternativas.length === 0 && (
        <p>No hay otras sedes cercanas con cupo disponible para tu dirección.</p>
      )}

      {datos && siguiente && (
        <p className="mt-3 font-medium">
          {datos.sede.nombre} vuelve a recibir pedidos {siguiente.texto}.
        </p>
      )}
      {datos && !siguiente && alternativas.length === 0 && (
        <p className="mt-3">Esta sede no tiene una franja próxima. Intenta más tarde.</p>
      )}
    </Modal>
  )
}
