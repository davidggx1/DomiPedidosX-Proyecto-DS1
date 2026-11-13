// HU-16 · Popup for new low stock alerts. Shown on any screen of the operator
export default function AvisosInventario({ avisos, alAbrir, alCerrar }) {
  if (avisos.length === 0) return null

  return (
    <div
      aria-live="assertive"
      className="fixed inset-x-0 top-2 z-50 mx-auto flex w-full max-w-md flex-col gap-2 px-4"
    >
      {avisos.map((aviso) => (
        <div
          key={aviso.id}
          role="alert"
          className="flex items-start gap-3 rounded-xl border-2 border-aviso bg-superficie p-4 shadow-lg"
        >
          <div className="flex-1">
            <p className="font-bold">⚠ {aviso.titulo}</p>
            <p className="text-sm text-texto-suave">{aviso.texto}</p>
            <button
              type="button"
              onClick={() => alAbrir(aviso)}
              className="mt-2 min-h-11 rounded-lg bg-marca px-4 py-2 font-medium text-sobre-marca hover:bg-marca-oscura"
            >
              Ver inventario
            </button>
          </div>
          <button
            type="button"
            onClick={() => alCerrar(aviso.id)}
            aria-label="Cerrar aviso"
            className="min-h-11 min-w-11 rounded-lg text-texto-suave hover:bg-superficie-alta"
          >
            ✕
          </button>
        </div>
      ))}
    </div>
  )
}
