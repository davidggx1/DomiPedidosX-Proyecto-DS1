import { Link, useLocation } from 'react-router-dom'

// Barra de pestañas con las opciones del rol actual (estilo del prototipo).
// En celular se muestra como lista vertical y solo cuando el menú está abierto.
// Un enlace puede indicar `activoEn` (otras rutas de su misma sección) para
// quedar resaltado también en esas páginas.
export default function Navegacion({ enlaces, abierto, alNavegar }) {
  const { pathname } = useLocation()

  return (
    <nav
      id="menu-principal"
      aria-label="Navegación principal"
      className={`border-b border-borde bg-superficie ${abierto ? 'block' : 'hidden'} sm:block`}
    >
      <ul className="mx-auto flex max-w-6xl flex-col gap-1 px-4 py-2 sm:flex-row sm:flex-wrap">
        {enlaces.map((enlace) => {
          // activo en su ruta exacta o en las páginas de su sección (activoEn)
          const activo =
            pathname.replace(/\/$/, '') === enlace.ruta || Boolean(enlace.activoEn?.includes(pathname))
          return (
            <li key={enlace.ruta}>
              <Link
                to={enlace.ruta}
                onClick={alNavegar}
                aria-current={activo ? 'page' : undefined}
                className={`flex min-h-11 items-center rounded-full px-4 text-sm transition-colors ${
                  activo
                    ? 'bg-marca font-semibold text-sobre-marca'
                    : 'text-texto-suave hover:bg-superficie-alta hover:text-texto'
                }`}
              >
                {enlace.texto}
              </Link>
            </li>
          )
        })}
      </ul>
    </nav>
  )
}
