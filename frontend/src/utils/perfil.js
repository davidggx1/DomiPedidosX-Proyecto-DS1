// Same rules as the backend (HU-02 and HU-07), checked before sending the form
export function validarPerfil({ nombres, apellidos, celular }) {
  const errores = {}
  if (!nombres.trim()) errores.nombres = 'Escribe tus nombres.'
  if (!apellidos.trim()) errores.apellidos = 'Escribe tus apellidos.'
  if (!/^\d{10}$/.test(celular.trim())) {
    errores.celular = 'El celular debe tener exactamente 10 dígitos numéricos.'
  }
  return errores
}
