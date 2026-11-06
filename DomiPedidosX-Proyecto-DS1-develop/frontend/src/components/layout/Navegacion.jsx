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
      <ul className="mx-auto flex max-w-6xl flex-col gap-2 px-4 py-3 sm:flex-row sm:flex-wrap">
        {enlaces.map((enlace) => (
          <li key={enlace.ruta}>
            <NavLink
              to={enlace.ruta}
              end
              onClick={alNavegar}
              className={({ isActive }) =>
                `flex min-h-11 items-center rounded-lg border px-4 transition-colors ${
                  isActive
                    ? 'border-white bg-marca font-semibold text-white'
                    : 'border-borde bg-fondo text-texto hover:bg-superficie-alta'
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
