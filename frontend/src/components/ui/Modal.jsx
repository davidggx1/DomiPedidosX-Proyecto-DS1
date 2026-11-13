import { useEffect, useId, useRef } from 'react'

// Ventana de diálogo sobre la página. Se cierra con Escape o tocando el fondo.
// El contenido va en children y los botones en `acciones`.
// Nunca es más alta que la pantalla: si el contenido no cabe, solo él se
// desplaza, y el título y los botones quedan siempre a la vista.
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

    // Mientras la ventana está abierta, la página de fondo no se desplaza.
    const desbordeAnterior = document.body.style.overflow
    document.body.style.overflow = 'hidden'

    return () => {
      document.removeEventListener('keydown', alPresionar)
      document.body.style.overflow = desbordeAnterior
      anterior?.focus?.()
    }
  }, [alCerrar])

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4"
      onClick={(evento) => evento.target === evento.currentTarget && alCerrar()}
    >
      <div
        ref={ventana}
        role="dialog"
        aria-modal="true"
        aria-labelledby={idTitulo}
        tabIndex={-1}
        className={`flex max-h-full w-full ${ancho} flex-col rounded-2xl border border-borde bg-superficie shadow-lg outline-none`}
      >
        <h2 id={idTitulo} className="px-6 pt-6 pb-3 text-lg font-bold">
          {titulo}
        </h2>
        <div className="min-h-0 flex-1 overflow-y-auto px-6 pb-2">{children}</div>
        {acciones && (
          <div className="flex flex-wrap justify-end gap-3 border-t border-borde px-6 py-4">{acciones}</div>
        )}
      </div>
    </div>
  )
}
