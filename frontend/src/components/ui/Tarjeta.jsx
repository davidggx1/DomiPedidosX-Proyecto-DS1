// Contenedor con el estilo de tarjeta del prototipo.
export default function Tarjeta({ titulo, children, className = '' }) {
  return (
    <section className={`rounded-2xl border border-borde bg-superficie p-5 shadow-sm ${className}`}>
      {titulo && <h2 className="mb-3 text-lg font-bold">{titulo}</h2>}
      {children}
    </section>
  )
}
