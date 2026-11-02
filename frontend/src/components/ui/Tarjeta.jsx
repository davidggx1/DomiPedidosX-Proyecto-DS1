// Contenedor con el estilo de tarjeta del prototipo.
export default function Tarjeta({ titulo, children, className = '' }) {
  return (
    <section className={`rounded-xl border border-borde bg-superficie p-4 ${className}`}>
      {titulo && <h2 className="mb-3 text-lg font-bold">{titulo}</h2>}
      {children}
    </section>
  )
}
