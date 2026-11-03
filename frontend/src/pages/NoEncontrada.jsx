import { Link } from 'react-router-dom'

export default function NoEncontrada() {
  return (
    <div className="flex flex-col gap-4">
      <h1 className="text-2xl font-bold">Página no encontrada</h1>
      <p className="text-texto-suave">La dirección que buscas no existe.</p>
      <Link to="/" className="self-start text-marca-clara underline underline-offset-4">
        Volver al inicio
      </Link>
    </div>
  )
}
