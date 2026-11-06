import { useEffect, useState } from 'react'
import { interpretarError } from '../../api/errores.js'
import { conectarMisEntregas, listarMisEntregas } from '../../api/repartidores.js'
import DisponibilidadRepartidor from '../../components/repartidor/DisponibilidadRepartidor.jsx'
import TarjetaEntrega from '../../components/repartidor/TarjetaEntrega.jsx'
import Alerta from '../../components/ui/Alerta.jsx'
import Tarjeta from '../../components/ui/Tarjeta.jsx'

// Home of the repartidor. The availability switch (HU-41) lives in the header
// and below are his orders in progress (HU-42), kept up to date by WebSocket
export default function MisEntregas() {
  const [entregas, setEntregas] = useState(null) // null while it loads
  const [error, setError] = useState(null)
  const [enVivo, setEnVivo] = useState(false)

  useEffect(() => {
    let vigente = true
    let ultimaConsulta = 0

    function cargar() {
      // if two messages arrive together, only the newest answer is shown
      const consulta = ++ultimaConsulta
      listarMisEntregas()
        .then((datos) => {
          if (!vigente || consulta !== ultimaConsulta) return
          setEntregas(datos)
          setError(null)
        })
        .catch((fallo) => {
          if (vigente) setError(interpretarError(fallo).general)
        })
    }

    cargar()
    // the message only says "something changed": the list is asked again
    const cerrar = conectarMisEntregas({
      alMensaje: cargar,
      alReconectar: cargar,
      alCambiarConexion: (conectado) => {
        if (vigente) setEnVivo(conectado)
      },
    })
    return () => {
      vigente = false
      cerrar()
    }
  }, [])

  return (
    <div className="flex flex-col gap-4">
      <header className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold">Mis entregas</h1>
          <p className="text-texto-suave">
            Activa tu disponibilidad para que el operador pueda asignarte pedidos.
          </p>
        </div>
        <DisponibilidadRepartidor />
      </header>

      <Tarjeta>
        <p className="text-sm text-texto-suave">
          Empiezas cada sesión como No disponible. Si te pones No disponible, no se te quitan los
          pedidos que ya tienes asignados: debes terminar esas entregas.
        </p>
      </Tarjeta>

      <Tarjeta>
        <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
          <h2 className="text-lg font-bold">Entregas asignadas</h2>
          <span
            className={`rounded-full border px-2 py-0.5 text-xs font-medium ${
              enVivo ? 'border-exito text-exito' : 'border-borde text-texto-suave'
            }`}
          >
            {enVivo ? 'En vivo' : 'Reconectando…'}
          </span>
        </div>

        {error && <Alerta tipo="error" titulo={error} className="mb-3" />}
        {entregas === null && !error && <p className="text-texto-suave">Cargando…</p>}
        {entregas?.length === 0 && (
          <p className="text-texto-suave">No tienes entregas en curso. Te avisaremos aquí cuando te asignen una.</p>
        )}
        {entregas?.length > 0 && (
          <ul className="flex flex-col gap-3">
            {entregas.map((entrega) => (
              <TarjetaEntrega key={entrega.id} entrega={entrega} />
            ))}
          </ul>
        )}
      </Tarjeta>
    </div>
  )
}
