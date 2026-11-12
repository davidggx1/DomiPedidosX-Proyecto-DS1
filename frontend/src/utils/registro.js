// Validación del formulario de registro de cliente (HU-01 y HU-02).
// El backend vuelve a validar todo; esto solo evita viajes innecesarios
// y da mensajes claros antes de enviar.

export const OPCIONES_TIPO_DOCUMENTO = [
  { valor: 'CC', etiqueta: 'Cédula de ciudadanía (C.C.)' },
  { valor: 'TI', etiqueta: 'Tarjeta de identidad (T.I.)' },
  { valor: 'CE', etiqueta: 'Cédula de extranjería (C.E.)' },
  { valor: 'PA', etiqueta: 'Pasaporte' },
  { valor: 'RC', etiqueta: 'Registro civil' },
  { valor: 'PPT', etiqueta: 'Permiso por Protección Temporal (PPT)' },
]

const REGEX_CORREO = /^[^\s@]+@[^\s@]+\.[^\s@]+$/
const REGEX_CELULAR = /^\d{10}$/
const TIPOS_VALIDOS = OPCIONES_TIPO_DOCUMENTO.map((opcion) => opcion.valor)

export const LONGITUD_MINIMA_CONTRASENA = 8

// Fecha local en formato AAAA-MM-DD (la que usa <input type="date">).
export function fechaHoy(hoy = new Date()) {
  const mes = String(hoy.getMonth() + 1).padStart(2, '0')
  const dia = String(hoy.getDate()).padStart(2, '0')
  return `${hoy.getFullYear()}-${mes}-${dia}`
}

export function soloDigitos(valor) {
  return String(valor ?? '').replace(/\D/g, '')
}

// Devuelve { campo: 'mensaje' }. Un objeto vacío significa que todo está bien.
export function validarRegistro(datos, hoy = new Date()) {
  const errores = {}
  const texto = (campo) => String(datos[campo] ?? '').trim()

  const email = texto('email')
  if (!email) errores.email = 'Escribe tu correo.'
  else if (!REGEX_CORREO.test(email)) errores.email = 'Escribe un correo válido.'

  const password = String(datos.password ?? '')
  if (!password) errores.password = 'Escribe una contraseña.'
  else if (password.length < LONGITUD_MINIMA_CONTRASENA) {
    errores.password = `La contraseña debe tener al menos ${LONGITUD_MINIMA_CONTRASENA} caracteres.`
  }

  if (!datos.confirmarPassword) errores.confirmarPassword = 'Confirma tu contraseña.'
  else if (datos.confirmarPassword !== password) {
    errores.confirmarPassword = 'Las contraseñas no coinciden.'
  }

  if (!datos.tipo_documento) errores.tipo_documento = 'Selecciona el tipo de documento.'
  else if (!TIPOS_VALIDOS.includes(datos.tipo_documento)) {
    errores.tipo_documento = 'Selecciona un tipo de documento válido.'
  }

  const documento = texto('num_documento')
  if (!documento) errores.num_documento = 'Escribe tu número de documento.'
  else if (documento.length > 12) {
    errores.num_documento = 'El número de documento no puede tener más de 12 caracteres.'
  }

  if (!texto('nombres')) errores.nombres = 'Escribe tus nombres.'
  if (!texto('apellidos')) errores.apellidos = 'Escribe tus apellidos.'

  const celular = texto('celular')
  if (!celular) errores.celular = 'El teléfono celular es obligatorio.'
  else if (!REGEX_CELULAR.test(celular)) {
    errores.celular = 'El número de teléfono debe contener exactamente 10 dígitos numéricos.'
  }

  const nacimiento = texto('fecha_nacimiento')
  if (!nacimiento) errores.fecha_nacimiento = 'Escribe tu fecha de nacimiento.'
  else if (nacimiento > fechaHoy(hoy)) {
    errores.fecha_nacimiento = 'La fecha de nacimiento no puede ser futura.'
  } else if (nacimiento < '1900-01-01') {
    errores.fecha_nacimiento = 'Escribe una fecha de nacimiento válida.'
  }

  return errores
}

// Cuerpo que espera POST /api/usuarios/registro/ (sin la confirmación de contraseña).
export function armarCuerpoRegistro(datos) {
  return {
    email: String(datos.email).trim().toLowerCase(),
    password: datos.password,
    tipo_documento: datos.tipo_documento,
    num_documento: String(datos.num_documento).trim(),
    nombres: String(datos.nombres).trim(),
    apellidos: String(datos.apellidos).trim(),
    celular: String(datos.celular).trim(),
    fecha_nacimiento: datos.fecha_nacimiento,
  }
}