// HU-61: turns the capacity state of the backend into what the screens need

const CODIGOS_CAPACIDAD = ['capacidad_maxima_alcanzada', 'franja_no_configurada']

// Block flag and message for a sede. Without data nothing is blocked,
// the backend still decides when the order is sent
export function interpretarCapacidad(estado) {
  if (!estado) {
    return { bloqueado: false, requiereConfirmacion: false, aviso: null }
  }

  if (estado.estado === 'saturada') {
    return {
      bloqueado: true,
      requiereConfirmacion: false,
      aviso: { tipo: 'error', texto: estado.mensaje },
    }
  }

  if (estado.estado === 'sin_franja') {
    // staff can confirm by hand, a customer cannot
    return {
      bloqueado: Boolean(estado.bloqueado),
      requiereConfirmacion: Boolean(estado.requiere_confirmacion),
      aviso: { tipo: estado.bloqueado ? 'error' : 'aviso', texto: estado.mensaje },
    }
  }

  return { bloqueado: false, requiereConfirmacion: false, aviso: null }
}

// Body of a capacity error (409) or null if the error is something else
export function errorDeCapacidad(error) {
  const datos = error?.response?.data
  if (error?.response?.status === 409 && CODIGOS_CAPACIDAD.includes(datos?.codigo)) {
    return datos
  }
  return null
}

// HU-60: umbral suggested for a slot, 80% of the limit and at least 1.
// Integer math, so 5 * 0.8 style rounding errors do not matter
export function umbralSugerido(maximo) {
  const limite = Number(maximo)
  if (!Number.isFinite(limite) || limite < 1) return 1
  return Math.max(1, Math.ceil((Math.floor(limite) * 4) / 5))
}

// Capacity state that comes inside a WebSocket event, or null for any other message
export function capacidadDeEvento(datos) {
  if (datos?.tipo !== 'capacidad_actualizada') return null
  return datos.capacidad ?? null
}

// What the capacity widget of the operator panel shows (HU-60)
export function describirCapacidad(capacidad) {
  if (!capacidad) return null

  if (capacidad.estado === 'sin_franja') {
    return {
      nivel: 'sin_franja',
      titulo: 'Sin franja de capacidad',
      texto: 'La sede no tiene una franja configurada para este día y hora.',
      porcentaje: null,
    }
  }

  const texto = `${capacidad.activos} de ${capacidad.maximo} pedidos ocupados`
  const porcentaje = capacidad.porcentaje ?? 0

  if (capacidad.estado === 'saturada') {
    return { nivel: 'saturada', titulo: 'Sede al 100% de su capacidad', texto, porcentaje }
  }
  if (capacidad.en_alerta) {
    return { nivel: 'alerta', titulo: 'Capacidad cercana al tope', texto, porcentaje }
  }
  return { nivel: 'normal', titulo: 'Capacidad de la franja', texto, porcentaje }
}
