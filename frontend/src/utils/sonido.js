// HU-40 · Alerta sonora sin archivos de audio: dos pitidos con la Web Audio API.
// Los navegadores no dejan sonar nada hasta que la persona toca la página una vez,
// así que el contexto de audio se crea (o se reactiva) en el primer toque.
let contexto = null

function obtenerContexto() {
  const Contexto = window.AudioContext || window.webkitAudioContext
  if (!Contexto) return null
  if (!contexto) contexto = new Contexto()
  return contexto
}

// Llamarla una vez al montar: habilita el sonido en el primer clic o toque.
export function prepararSonido() {
  const desbloquear = () => obtenerContexto()?.resume()
  window.addEventListener('pointerdown', desbloquear, { once: true })
  return () => window.removeEventListener('pointerdown', desbloquear)
}

function pitido(ctx, inicio, frecuencia) {
  const oscilador = ctx.createOscillator()
  const volumen = ctx.createGain()
  oscilador.frequency.value = frecuencia
  volumen.gain.setValueAtTime(0.25, inicio)
  volumen.gain.exponentialRampToValueAtTime(0.001, inicio + 0.25)
  oscilador.connect(volumen).connect(ctx.destination)
  oscilador.start(inicio)
  oscilador.stop(inicio + 0.25)
}

export function sonarAviso() {
  try {
    const ctx = obtenerContexto()
    if (!ctx || ctx.state !== 'running') return
    pitido(ctx, ctx.currentTime, 880)
    pitido(ctx, ctx.currentTime + 0.3, 1175)
    navigator.vibrate?.([200, 100, 200]) // en celulares que lo permiten
  } catch {
    // sin sonido el aviso en pantalla sigue funcionando
  }
}
