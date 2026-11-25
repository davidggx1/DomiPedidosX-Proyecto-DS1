// Íconos de categoría del menú (SVG propios, sin dependencias).
// Se elige por palabras del nombre; si no hay coincidencia, se usa un cubierto.

const TRAZOS = {
  bebida: ['M6 8h12l-1.5 12h-9z', 'M5 8h14', 'M12 8V3l3-1'],
  hamburguesa: [
    'M4 11a8 5 0 0 1 16 0z',
    'M3 14h18',
    'M4 17h16',
    'M5 17v1a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2v-1',
  ],
  pizza: ['M3 6c6-3 12-3 18 0L12 21z', 'M10 9h.01', 'M14 10h.01', 'M12 14h.01'],
  papas: ['M6 10l1.5 11h9L18 10z', 'M8 10V4', 'M12 10V3', 'M16 10V5'],
  postre: ['M7 11a5 5 0 0 1 10 0z', 'M8 11l4 10 4-10'],
  combo: ['M4 9h16v11H4z', 'M3 6h18v3H3z', 'M12 6v14'],
  cubiertos: ['M7 3v8', 'M5 3v5a2 2 0 0 0 4 0V3', 'M7 11v10', 'M17 3c-2 2-2 6 0 8v10'],
}

const PALABRAS = [
  ['bebida', ['bebida', 'gaseosa', 'jugo', 'limonada', 'malteada', 'cafe', 'te ']],
  ['hamburguesa', ['hamburguesa', 'burger']],
  ['pizza', ['pizza']],
  ['papas', ['papa', 'acompan', 'entrada', 'snack', 'frito']],
  ['postre', ['postre', 'helado', 'dulce']],
  ['combo', ['combo', 'promo']],
]

function tipoIcono(nombre = '') {
  const texto = `${nombre} `
    .toLowerCase()
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
  const encontrado = PALABRAS.find(([, claves]) => claves.some((clave) => texto.includes(clave)))
  return encontrado ? encontrado[0] : 'cubiertos'
}

export default function IconoCategoria({ nombre, className = 'size-8' }) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.5"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      className={className}
    >
      {TRAZOS[tipoIcono(nombre)].map((d) => (
        <path key={d} d={d} />
      ))}
    </svg>
  )
}