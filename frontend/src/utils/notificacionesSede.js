// HU-83 · Notificaciones de la sede. Mismos valores que sedes/models.py (EventoSede y RolSuscrito).

export const EVENTOS_SEDE = [
  {
    valor: 'stock_bajo',
    titulo: 'Alerta de stock bajo',
    descripcion: 'Un producto o ingrediente llega a su stock mínimo.',
  },
  {
    valor: 'cancelacion',
    titulo: 'Pedido cancelado',
    descripcion: 'Un pedido de la sede se cancela (cliente, sede o sistema).',
  },
  {
    valor: 'sobrecupo',
    titulo: 'Sobrecupo de capacidad',
    descripcion: 'La sede llega al umbral de alerta de su franja de capacidad.',
  },
]

export const ROLES_SUSCRIBIBLES = [
  { valor: 'administrador', etiqueta: 'Administradores' },
  { valor: 'operador', etiqueta: 'Operadores' },
  { valor: 'cocina', etiqueta: 'Cocina' },
  { valor: 'repartidor', etiqueta: 'Repartidores' },
]

const PATRON_CORREO = /^[^\s@]+@[^\s@]+\.[^\s@]+$/

// Agrupa la lista de la API por evento: { stock_bajo: { roles: {operador: sus}, correos: [sus] }, ... }
export function agruparPorEvento(suscripciones) {
  const grupos = Object.fromEntries(EVENTOS_SEDE.map(({ valor }) => [valor, { roles: {}, correos: [] }]))
  for (const suscripcion of suscripciones) {
    const grupo = grupos[suscripcion.evento]
    if (!grupo) continue
    if (suscripcion.rol) grupo.roles[suscripcion.rol] = suscripcion
    else grupo.correos.push(suscripcion)
  }
  for (const grupo of Object.values(grupos)) grupo.correos.sort((a, b) => a.correo.localeCompare(b.correo))
  return grupos
}

// Mensaje de error del correo nuevo, o null si se puede agregar
export function validarCorreoNuevo(texto, correosActuales) {
  const correo = texto.trim().toLowerCase()
  if (!correo) return 'Escribe un correo.'
  if (!PATRON_CORREO.test(correo)) return 'Escribe un correo válido, por ejemplo gerente@empresa.com.'
  if (correosActuales.some((s) => s.correo === correo)) return 'Ese correo ya recibe este aviso.'
  return null
}

// "Nadie", "Operadores", "Operadores y 2 correos"...
export function resumenDestinatarios(grupo) {
  const partes = ROLES_SUSCRIBIBLES.filter(({ valor }) => grupo.roles[valor]).map(({ etiqueta }) => etiqueta)
  const n = grupo.correos.length
  if (n) partes.push(n === 1 ? '1 correo' : `${n} correos`)
  if (!partes.length) return 'Nadie recibe este aviso por correo'
  return `Lo reciben: ${partes.length === 1 ? partes[0] : `${partes.slice(0, -1).join(', ')} y ${partes.at(-1)}`}`
}
