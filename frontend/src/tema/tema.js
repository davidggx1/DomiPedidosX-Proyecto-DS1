// Tema claro u oscuro de la app.
// La elección de la persona se guarda en el navegador. Si nunca eligió,
// se usa la preferencia de su sistema operativo (modo oscuro de Windows, del celular...).

export const TEMAS = { CLARO: 'claro', OSCURO: 'oscuro' }
export const CLAVE_TEMA = 'domipedidosx:tema'

export function esTemaValido(valor) {
  return valor === TEMAS.CLARO || valor === TEMAS.OSCURO
}

// Tema a usar: el que la persona guardó, o si no, el de su sistema.
export function resolverTema(guardado, sistemaPrefiereOscuro) {
  if (esTemaValido(guardado)) return guardado
  return sistemaPrefiereOscuro ? TEMAS.OSCURO : TEMAS.CLARO
}

export function temaContrario(tema) {
  return tema === TEMAS.OSCURO ? TEMAS.CLARO : TEMAS.OSCURO
}

// --- Acceso al navegador ------------------------------------------------------

export function leerTemaGuardado() {
  try {
    return localStorage.getItem(CLAVE_TEMA)
  } catch {
    return null // modo privado o almacenamiento bloqueado
  }
}

export function guardarTema(tema) {
  try {
    localStorage.setItem(CLAVE_TEMA, tema)
  } catch {
    // sin almacenamiento el tema dura solo esta visita
  }
}

export function sistemaPrefiereOscuro() {
  return window.matchMedia?.('(prefers-color-scheme: dark)').matches ?? true
}

export function aplicarTema(tema) {
  document.documentElement.dataset.tema = tema
}
