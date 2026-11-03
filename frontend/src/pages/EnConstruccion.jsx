import Tarjeta from '../components/ui/Tarjeta.jsx'

// Página temporal para las rutas cuyas historias aún no se implementan.
// Cada integrante la reemplaza por su página real al desarrollar su HU.
export default function EnConstruccion({ titulo, historias }) {
  return (
    <div className="flex flex-col gap-4">
      <h1 className="text-2xl font-bold">{titulo}</h1>
      <Tarjeta>
        <p>Esta sección está en desarrollo.</p>
        {historias && (
          <p className="mt-2 text-sm text-texto-suave">Historias de usuario: {historias}</p>
        )}
      </Tarjeta>
    </div>
  )
}
