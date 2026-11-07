const VARIANTES = {
  primario: 'bg-marca text-white hover:bg-marca-oscura',
  secundario: 'border border-borde bg-superficie-alta text-texto hover:bg-borde',
  peligro: 'border border-error bg-transparent text-error hover:bg-error/10',
  fantasma: 'bg-transparent text-texto hover:bg-superficie-alta',
}

// Botón base. Altura mínima de 44 px para que sea fácil de tocar en celular.
export default function Boton({
  variante = 'primario',
  tipo = 'button',
  cargando = false,
  disabled = false,
  className = '',
  children,
  ...props
}) {
  return (
    <button
      type={tipo}
      disabled={disabled || cargando}
      aria-busy={cargando || undefined}
      className={`inline-flex min-h-11 items-center justify-center gap-2 rounded-lg px-4 py-2 font-medium transition-colors disabled:cursor-not-allowed disabled:opacity-50 ${VARIANTES[variante]} ${className}`}
      {...props}
    >
      {cargando ? 'Procesando…' : children}
    </button>
  )
}
