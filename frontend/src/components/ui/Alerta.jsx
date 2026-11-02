const ESTILOS = {
  error: { clases: 'border-error text-error', icono: '✕', rol: 'alert' },
  exito: { clases: 'border-exito text-exito', icono: '✓', rol: 'status' },
  aviso: { clases: 'border-aviso text-aviso', icono: '⚠', rol: 'status' },
  info: { clases: 'border-borde text-texto', icono: 'ℹ', rol: 'status' },
}

// Mensaje para el usuario. Los lectores de pantalla lo anuncian al aparecer:
// los errores de inmediato (role="alert") y el resto de forma cortés (role="status").
export default function Alerta({ tipo = 'info', titulo, children, className = '' }) {
  const estilo = ESTILOS[tipo]

  return (
    <div
      role={estilo.rol}
      className={`flex gap-3 rounded-lg border bg-superficie px-4 py-3 ${estilo.clases} ${className}`}
    >
      <span aria-hidden="true" className="font-bold">
        {estilo.icono}
      </span>
      <div>
        {titulo && <p className="font-semibold">{titulo}</p>}
        {children && <div className="text-texto">{children}</div>}
      </div>
    </div>
  )
}
