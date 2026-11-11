// Reglas de tarifa y tiempo de una zona (HU-56).

const vacio = (valor) => String(valor ?? '').trim() === ''

// El formulario está listo para activar la zona cuando tiene tarifa y tiempo.
export function formularioConfigurado(valores) {
  return !vacio(valores.tarifa_domicilio) && !vacio(valores.tiempo_estimado)
}

// Una zona guardada está configurada cuando el backend trae ambos valores.
export function zonaConfigurada(zona) {
  return zona.tarifa_domicilio != null && zona.tiempo_estimado != null
}

// Devuelve { campo: mensaje }; vacío si todo está bien.
// Los vacíos solo se aceptan si la zona queda desactivada.
export function validarTarifaTiempo({ tarifa_domicilio, tiempo_estimado, activo }) {
  const errores = {}
  const tarifa = String(tarifa_domicilio ?? '').trim()
  const tiempo = String(tiempo_estimado ?? '').trim()

  if (tarifa === '') {
    if (activo) errores.tarifa_domicilio = 'Obligatoria para activar la zona.'
  } else if (!/^\d+(\.\d{1,2})?$/.test(tarifa)) {
    errores.tarifa_domicilio = 'Ingresa un número válido (0 o más), sin letras ni negativos.'
  }

  if (tiempo === '') {
    if (activo) errores.tiempo_estimado = 'Obligatorio para activar la zona.'
  } else if (!/^\d+$/.test(tiempo) || Number(tiempo) <= 0) {
    errores.tiempo_estimado = 'Debe ser un número entero de minutos mayor que 0.'
  }

  return errores
}

export function formatearTarifa(valor) {
  return valor == null ? 'Sin tarifa' : `$${Number(valor).toLocaleString('es-CO')}`
}

export function formatearTiempo(valor) {
  return valor == null ? 'Sin tiempo' : `${valor} min`
}