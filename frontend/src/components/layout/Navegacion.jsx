import { NavLink } from 'react-router-dom'

// Barra de pestañas con las opciones del rol actual (estilo del prototipo).
// En celular se muestra como lista vertical y solo cuando el menú está abierto.
export default function Navegacion({ enlaces, abierto, alNavegar }) {
  return (
    <nav
      id="menu-principal"
      aria-label="Navegación principal"
      className={`border-b border-borde bg-superficie ${abierto ? 'block' : 'hidden'} sm:block`}
    >
      <ul className="mx-auto flex max-w-6xl flex-col gap-1 px-4 py-2 sm:flex-row sm:flex-wrap">
        {enlaces.map((enlace) => (
          <li key={enlace.ruta}>
            <NavLink
              to={enlace.ruta}
              end
              onClick={alNavegar}
              className={({ isActive }) =>
                `flex min-h-11 items-center rounded-full px-4 text-sm transition-colors ${
                  isActive
                    ? 'bg-marca font-semibold text-sobre-marca'
                    : 'text-texto-suave hover:bg-superficie-alta hover:text-texto'
                }`
              }
            >
              {enlace.texto}
            </NavLink>
          </li>
        ))}
      </ul>
    </nav>
  )
}
