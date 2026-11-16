// HU-85 · Lógica de los combos sin React, para poder probarla con Vitest.
//
// Un combo llega del backend así:
// {
//   id, sede_id, sede_nombre, nombre, descripcion, condicion, precio: '20000.00',
//   fecha_inicio, fecha_vencimiento, activo,
//   productos_detalle: [{ producto, nombre, cantidad, precio_base, disponible, motivo }],
//   suma_individual: '23000.00', ahorro: '3000.00',
//   disponible, motivo_no_disponible, cupo_max_diario, usos_hoy, cupo_restante,
// }

export const FILTROS_COMBO = [
  { valor: 'todos', etiqueta: 'Todos' },
  { valor: 'disponible', etiqueta: 'Disponibles' },
  { valor: 'no_disponible', etiqueta: 'No disponibles' },
  { valor: 'inactivo', etiqueta: 'Inactivos' },
]

export const ETIQUETA_ESTADO_COMBO = {
  disponible: 'Disponible',
  no_disponible: 'No disponible',
  inactivo: 'Inactivo',
}

export function estadoCombo(combo) {
  if (!combo.activo) return 'inactivo'
  return combo.disponible ? 'disponible' : 'no_disponible'
}

export function contarPorEstadoCombo(combos) {
  const conteo = { todos: combos.length, disponible: 0, no_disponible: 0, inactivo: 0 }
  for (const combo of combos) conteo[estadoCombo(combo)] += 1
  return conteo
}

export function filtrarCombos(combos, filtro) {
  if (!filtro || filtro === 'todos') return combos
  return combos.filter((combo) => estadoCombo(combo) === filtro)
}

export function claseEstadoCombo(estado) {
  if (estado === 'disponible') return 'border-exito text-exito'
  if (estado === 'no_disponible') return 'border-aviso text-aviso'
  return 'border-borde text-texto-suave'
}

export function normalizarPrecio(texto) {
  return String(texto ?? '').trim().replace(',', '.')
}

// lineas = { [productoId]: cantidad }. Solo cuentan las de cantidad entera > 0.
export function lineasValidas(lineas) {
  return Object.entries(lineas)
    .map(([producto, cantidad]) => ({ producto: Number(producto), cantidad: Number(cantidad) }))
    .filter((linea) => Number.isInteger(linea.cantidad) && linea.cantidad > 0)
}

// Suma de precio_base × cantidad de los productos elegidos. `productos` = lista del menú.
export function sumaIndividual(lineas, productos) {
  const porId = new Map(productos.map((producto) => [producto.id, Number(producto.precio_base)]))
  return lineasValidas(lineas).reduce(
    (total, linea) => total + (porId.get(linea.producto) ?? 0) * linea.cantidad,
    0,
  )
}

export function totalUnidades(lineas) {
  return lineasValidas(lineas).reduce((total, linea) => total + linea.cantidad, 0)
}

// Ahorro del cliente frente a comprar los productos sueltos; null si aún no se puede calcular.
export function ahorroCombo(precio, suma) {
  const numero = Number(normalizarPrecio(precio))
  if (!normalizarPrecio(precio) || Number.isNaN(numero) || suma <= 0) return null
  return suma - numero
}

// Devuelve { campo: 'mensaje' }; vacío significa que todo está bien.
// Son las mismas reglas del backend: el servidor vuelve a validar.
export function validarCombo(datos, productos) {
  const errores = {}

  const nombre = String(datos.nombre ?? '').trim()
  if (!nombre) errores.nombre = 'Escribe el nombre del combo.'
  else if (nombre.length > 100) errores.nombre = 'El nombre no puede tener más de 100 caracteres.'

  const unidades = totalUnidades(datos.lineas ?? {})
  if (unidades < 2) errores.productos = 'Elige al menos 2 productos (o un producto en cantidad 2).'

  const texto = normalizarPrecio(datos.precio)
  if (!texto) {
    errores.precio = 'Escribe el precio del combo.'
  } else if (!/^\d+(\.\d+)?$/.test(texto)) {
    errores.precio = 'Escribe un número válido.'
  } else {
    const numero = Number(texto)
    const decimales = texto.split('.')[1] ?? ''
    const suma = sumaIndividual(datos.lineas ?? {}, productos)
    if (numero <= 0) errores.precio = 'El precio debe ser mayor que 0.'
    else if (decimales.length > 2) errores.precio = 'Usa máximo 2 decimales.'
    else if (unidades >= 2 && numero >= suma) {
      errores.precio = `El precio debe ser menor que el total individual ($${suma.toLocaleString('es-CO')}).`
    }
  }

  if (!datos.fecha_inicio) errores.fecha_inicio = 'Elige la fecha de inicio.'
  if (!datos.fecha_vencimiento) errores.fecha_vencimiento = 'Elige la fecha de fin.'
  else if (datos.fecha_inicio && datos.fecha_vencimiento < datos.fecha_inicio) {
    errores.fecha_vencimiento = 'La fecha de fin no puede ser anterior a la de inicio.'
  }

  const cupo = String(datos.cupo_max_diario ?? '').trim()
  if (cupo && (!/^\d+$/.test(cupo) || Number(cupo) <= 0 || cupo.length > 9)) {
    errores.cupo_max_diario = 'El cupo debe ser un entero mayor que 0 (vacío = sin límite).'
  }

  return errores
}

// Cuerpo que espera POST/PATCH /api/combos/. La sede la pone el backend (o el administrador).
export function armarCuerpoCombo(datos) {
  const cupo = String(datos.cupo_max_diario ?? '').trim()
  return {
    nombre: String(datos.nombre).trim(),
    descripcion: String(datos.descripcion ?? '').trim(),
    condicion: String(datos.condicion ?? '').trim(),
    precio: normalizarPrecio(datos.precio),
    fecha_inicio: datos.fecha_inicio,
    fecha_vencimiento: datos.fecha_vencimiento,
    productos: lineasValidas(datos.lineas ?? {}),
    cupo_max_diario: cupo ? Number(cupo) : null,
  }
}

function fechaLocal(hoy = new Date()) {
  const mes = String(hoy.getMonth() + 1).padStart(2, '0')
  const dia = String(hoy.getDate()).padStart(2, '0')
  return `${hoy.getFullYear()}-${mes}-${dia}`
}

// Valores iniciales del formulario: los del combo que se edita, o los de uno nuevo.
export function datosInicialesCombo(combo, hoy = new Date()) {
  if (!combo) {
    return {
      nombre: '',
      descripcion: '',
      condicion: '',
      precio: '',
      fecha_inicio: fechaLocal(hoy),
      fecha_vencimiento: '',
      cupo_max_diario: '',
      lineas: {},
    }
  }
  return {
    nombre: combo.nombre,
    descripcion: combo.descripcion ?? '',
    condicion: combo.condicion ?? '',
    precio: String(Number(combo.precio)),
    fecha_inicio: combo.fecha_inicio,
    fecha_vencimiento: combo.fecha_vencimiento,
    cupo_max_diario: combo.cupo_max_diario == null ? '' : String(combo.cupo_max_diario),
    lineas: Object.fromEntries(
      (combo.productos_detalle ?? []).map((linea) => [linea.producto, String(linea.cantidad)]),
    ),
  }
}

// Productos del menú que se pueden elegir (activos). Acepta lista o respuesta paginada.
export function productosElegibles(respuesta) {
  const lista = Array.isArray(respuesta) ? respuesta : (respuesta?.results ?? [])
  return lista.filter((producto) => producto.activo !== false)
}