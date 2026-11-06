import DisponibilidadRepartidor from '../../components/repartidor/DisponibilidadRepartidor.jsx'
import Tarjeta from '../../components/ui/Tarjeta.jsx'

// Home of the repartidor. The availability switch (HU-41) lives in the header
export default function MisEntregas() {
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

      <Tarjeta titulo="Entregas asignadas">
        <p>Esta sección está en desarrollo.</p>
        <p className="mt-2 text-sm text-texto-suave">Historias de usuario: HU-42, HU-43, HU-45</p>
      </Tarjeta>
    </div>
  )
}
