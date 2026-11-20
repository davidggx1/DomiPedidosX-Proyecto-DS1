// Tarjeta con una cifra grande del resumen de un reporte (HU-71, HU-72)
export default function Cifra({ titulo, valor, detalle }) {
  return (
    <div className="rounded-2xl border border-borde bg-superficie p-4">
      <p className="text-sm text-texto-suave">{titulo}</p>
      <p className="mt-1 font-titulo text-3xl font-bold">{valor}</p>
      {detalle && <p className="mt-1 text-sm text-texto-suave">{detalle}</p>}
    </div>
  )
}
