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
