export default function TimerEstimadoEntrega({
  rango,
  desglose = null,
  estadoPedido = null,
  fechaCreacion = null,
}) {
  if (!rango) return null

  const esAltaCarga = desglose?.nivel_carga_cocina === 'alta'
  const esModerada = desglose?.nivel_carga_cocina === 'moderada'

  // En tracking, si tenemos fechaCreacion, mostramos también la hora aproximada de llegada
  let ventanaHoraria = null
  if (fechaCreacion) {
    const [minStr, maxStr] = rango.replace(' min', '').split('-')
    const base = new Date(fechaCreacion).getTime()
    if (!Number.isNaN(base) && minStr && maxStr) {
      const fmt = (ms) =>
        new Date(ms).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
      ventanaHoraria = `${fmt(base + Number(minStr) * 60000)} – ${fmt(base + Number(maxStr) * 60000)}`
    }
  }

  return (
    <div className="flex flex-col gap-1.5 rounded-xl border border-borde bg-superficie p-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <span className="text-sm font-medium text-texto-suave">Tiempo estimado de entrega</span>
        <span className="inline-flex items-center gap-1.5 rounded-full bg-marca/10 px-3 py-1 text-base font-bold text-marca">
          ⏱ {rango}
        </span>
      </div>

      {ventanaHoraria && estadoPedido && !['entregado', 'cancelado'].includes(estadoPedido) && (
        <p className="text-xs text-texto-suave">
          Llegada aproximada entre <strong className="text-texto">{ventanaHoraria}</strong>
        </p>
      )}

      {desglose && (
        <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-texto-suave">
          <span>Preparación: {desglose.preparacion_min} min</span>
          <span>·</span>
          <span>Zona: {desglose.zona_min} min</span>
          {desglose.congestion_min > 0 && (
            <>
              <span>·</span>
              <span className={esAltaCarga ? 'font-semibold text-error' : esModerada ? 'font-medium text-aviso' : ''}>
                Cocina ({desglose.pedidos_activos_cocina} en cola): +{desglose.congestion_min} min
              </span>
            </>
          )}
        </div>
      )}
    </div>
  )
}