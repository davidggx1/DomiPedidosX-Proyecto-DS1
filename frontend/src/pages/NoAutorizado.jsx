import { Link } from 'react-router-dom'
import Alerta from '../components/ui/Alerta.jsx'

export default function NoAutorizado() {
  return (
    <div className="flex max-w-xl flex-col gap-4">
      <h1 className="text-2xl font-bold">Acceso no autorizado</h1>
      <Alerta tipo="error" titulo="No tienes permiso para ver esta página.">
        Esta sección pertenece a otro rol.
      </Alerta>
      <Link to="/" className="self-start text-marca-clara underline underline-offset-4">
        Volver a mi página de inicio
      </Link>
    </div>
  )
}
