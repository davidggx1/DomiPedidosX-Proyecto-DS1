import { useEffect, useId, useRef } from 'react'

// Ventana de diálogo sobre la página. Se cierra con Escape o tocando el fondo.
// El contenido va en children y los botones en `acciones`.
export default function Modal({ titulo, alCerrar, acciones, ancho = 'max-w-md', children }) {
  const idTitulo = useId()
  const ventana = useRef(null)

  useEffect(() => {
    // Lleva el foco al diálogo y lo devuelve a donde estaba al cerrarse.
    const anterior = document.activeElement
    ventana.current?.focus()

    function alPresionar(evento) {
      if (evento.key === 'Escape') alCerrar()
    }
    document.addEventListener('keydown', alPresionar)
    return () => {
      document.removeEventListener('keydown', alPresionar)
      anterior?.focus?.()
    }
  }, [alCerrar])

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center overflow-y-auto bg-black/60 p-4"
      onClick={(evento) => evento.target === evento.currentTarget && alCerrar()}
    >
      <div
        ref={ventana}
        role="dialog"
        aria-modal="true"
        aria-labelledby={idTitulo}
        tabIndex={-1}
        className={`my-8 w-full ${ancho} rounded-xl border border-borde bg-superficie p-6 shadow-lg outline-none`}
      >
        <h2 id={idTitulo} className="text-lg font-bold">
          {titulo}
        </h2>
        <div className="mt-3">{children}</div>
        {acciones && <div className="mt-6 flex flex-wrap justify-end gap-3">{acciones}</div>}
      </div>
    </div>
  )
}
