// HU-84 · Lógica de las promociones sin React, para poder probarla con Vitest.
//
// Una promoción llega del backend así:
// {
//   id, sede, sede_nombre, nombre, descripcion,
//   tipo_descuento: 'porcentaje' | 'valor_fijo', valor: '15.00',
//   fecha_inicio: '2026-11-15', fecha_fin: '2026-11-22', condiciones, activa,
//   estado: 'vigente' | 'programada' | 'vencida' | 'inactiva', utilizable,
// }

export const TIPOS_DESCUENTO = [
  { valor: 'porcentaje', etiqueta: 'Porcentaje (%)' },
  { valor: 'valor_fijo', etiqueta: 'Valor fijo ($)' },
]

export const FILTROS_ESTADO = [
  { valor: 'todas', etiqueta: 'Todas' },
  { valor: 'vigente', etiqueta: 'Vigentes' },
  { valor: 'programada', etiqueta: 'Programadas' },
  { valor: 'vencida', etiqueta: 'Vencidas' },
  { valor: 'inactiva', etiqueta: 'Inactivas' },
]

export const ETIQUETA_ESTADO = {
  vigente: 'Vigente',
  programada: 'Programada',
  vencida: 'Vencida',
  inactiva: 'Inactiva',
}

const TIPOS_VALIDOS = TIPOS_DESCUENTO.map((tipo) => tipo.valor)

// Fecha local en formato AAAA-MM-DD (la que usa <input type="date">).
export function fechaLocal(hoy = new Date()) {
  const mes = String(hoy.getMonth() + 1).padStart(2, '0')
  const dia = String(hoy.getDate()).padStart(2, '0')
  return `${hoy.getFullYear()}-${mes}-${dia}`
}

// "2026-11-15" → "15/11/2026", sin pasar por Date para no correr el día por la zona horaria.
export function formatearFecha(texto) {
  const [anio, mes, dia] = String(texto ?? '').split('-')
  return anio && mes && dia ? `${dia}/${mes}/${anio}` : ''
}

export function textoVigencia(promocion) {
  return `${formatearFecha(promocion.fecha_inicio)} – ${formatearFecha(promocion.fecha_fin)}`
}

// El valor se escribe con punto o con coma decimal.
export function normalizarValor(texto) {
  return String(texto ?? '').trim().replace(',', '.')
}

export function etiquetaValor(tipo) {
  return tipo === 'valor_fijo' ? 'Valor del descuento ($)' : 'Porcentaje de descuento (%)'
}

// "15.00" → "15 %", "12.50" → "12.5 %"
export function textoPorcentaje(valor) {
  return `${Number(valor)} %`
}

// Devuelve { campo: 'mensaje' }; vacío significa que todo está bien.
// Son las mismas reglas del backend: el servidor vuelve a validar.
export function validarPromocion(datos) {
  const errores = {}

  const nombre = String(datos.nombre ?? '').trim()
  if (!nombre) errores.nombre = 'Escribe el nombre de la promoción.'
  else if (nombre.length > 100) errores.nombre = 'El nombre no puede tener más de 100 caracteres.'

  if (!TIPOS_VALIDOS.includes(datos.tipo_descuento)) {
    errores.tipo_descuento = 'Selecciona el tipo de descuento.'
  }

  const texto = normalizarValor(datos.valor)
  if (!texto) {
    errores.valor = 'Escribe el valor del descuento.'
  } else if (!/^-?\d+(\.\d+)?$/.test(texto)) {
    errores.valor = 'Escribe un número válido.'
  } else {
    const numero = Number(texto)
    const [entero, decimales = ''] = texto.replace('-', '').split('.')
    if (numero <= 0) errores.valor = 'El descuento debe ser mayor que 0.'
    else if (decimales.length > 2) errores.valor = 'Usa máximo 2 decimales.'
    else if (entero.length > 8) errores.valor = 'El valor es demasiado grande.'
    else if (datos.tipo_descuento === 'porcentaje' && numero > 100) {
      errores.valor = 'El porcentaje no puede ser mayor que 100.'
    }
  }

  if (!datos.fecha_inicio) errores.fecha_inicio = 'Elige la fecha de inicio.'
  if (!datos.fecha_fin) errores.fecha_fin = 'Elige la fecha de fin.'
  else if (datos.fecha_inicio && datos.fecha_fin < datos.fecha_inicio) {
    errores.fecha_fin = 'La fecha de fin no puede ser anterior a la de inicio.'
  }

  return errores
}

// Cuerpo que espera POST/PATCH /api/promociones/. La sede la pone el backend.
export function armarCuerpoPromocion(datos) {
  return {
    nombre: String(datos.nombre).trim(),
    descripcion: String(datos.descripcion ?? '').trim(),
    tipo_descuento: datos.tipo_descuento,
    valor: normalizarValor(datos.valor),
    fecha_inicio: datos.fecha_inicio,
    fecha_fin: datos.fecha_fin,
    condiciones: String(datos.condiciones ?? '').trim(),
  }
}

// Valores iniciales del formulario: los de la promoción que se edita, o los de una nueva.
export function datosIniciales(promocion, hoy = new Date()) {
  if (!promocion) {
    return {
      nombre: '',
      descripcion: '',
      tipo_descuento: 'porcentaje',
      valor: '',
      fecha_inicio: fechaLocal(hoy),
      fecha_fin: '',
      condiciones: '',
    }
  }
  return {
    nombre: promocion.nombre,
    descripcion: promocion.descripcion ?? '',
    tipo_descuento: promocion.tipo_descuento,
    valor: String(Number(promocion.valor)),
    fecha_inicio: promocion.fecha_inicio,
    fecha_fin: promocion.fecha_fin,
    condiciones: promocion.condiciones ?? '',
  }
}

export function contarPorEstado(promociones) {
  const conteo = { todas: promociones.length, vigente: 0, programada: 0, vencida: 0, inactiva: 0 }
  for (const promocion of promociones) {
    if (promocion.estado in conteo) conteo[promocion.estado] += 1
  }
  return conteo
}

export function filtrarPorEstado(promociones, filtro) {
  if (!filtro || filtro === 'todas') return promociones
  return promociones.filter((promocion) => promocion.estado === filtro)
}

// Colores de la etiqueta de estado (clases de Tailwind que ya usa el proyecto).
export function claseEstado(estado) {
  if (estado === 'vigente') return 'border-exito text-exito'
  if (estado === 'programada') return 'border-aviso text-aviso'
  return 'border-borde text-texto-suave'
}