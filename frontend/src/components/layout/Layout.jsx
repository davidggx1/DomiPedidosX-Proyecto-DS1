import { useState } from 'react'
import { Link, Outlet, useNavigate } from 'react-router-dom'
import AlertasInventarioProvider from '../../alertas/AlertasInventarioProvider.jsx'
import { useAuth } from '../../auth/useAuth.js'
import { ENLACES_POR_ROL, ETIQUETA_ROL, ROLES } from '../../auth/roles.js'
import { useCarrito } from '../../carrito/useCarrito.js'
import AvisosRepartidor from '../repartidor/AvisosRepartidor.jsx'
import Navegacion from './Navegacion.jsx'

// Estructura común de todas las páginas: encabezado, navegación por rol,
// contenido principal y pie de página.
export default function Layout() {
  const { usuario, cerrarSesion } = useAuth()
  const navegar = useNavigate()
  const [menuAbierto, setMenuAbierto] = useState(false)
  const { articulos } = useCarrito()

  const enlaces = usuario ? (ENLACES_POR_ROL[usuario.rol] ?? []) : []

  function manejarCerrarSesion() {
    cerrarSesion()
    setMenuAbierto(false)
    navegar('/login')
  }

  const contenido = (
    <main id="contenido" tabIndex={-1} className="mx-auto w-full max-w-6xl flex-1 px-4 py-6">
      <Outlet />
    </main>
  )

  return (
    <div className="flex min-h-screen flex-col">
      <a
        href="#contenido"
        className="sr-only focus:not-sr-only focus:fixed focus:top-2 focus:left-2 focus:z-50 focus:rounded-lg focus:bg-texto focus:px-4 focus:py-2 focus:text-fondo"
      >
        Saltar al contenido
      </a>

      <header className="bg-marca text-white">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-3 px-4 py-3">
          <Link to="/" className="text-lg font-bold sm:text-xl">
            DomiPedidosX
          </Link>

          {usuario ? (
            <div className="flex flex-wrap items-center justify-end gap-2 sm:gap-3">
              <p className="hidden text-sm sm:block">
                {usuario.nombre}
                <span className="opacity-80"> · {ETIQUETA_ROL[usuario.rol]}</span>
              </p>
              {usuario.rol === ROLES.CLIENTE && (
                <Link
                  to="/carrito"
                  aria-label={`Carrito, ${articulos} ${articulos === 1 ? 'producto' : 'productos'}`}
                  className="flex min-h-11 items-center gap-2 rounded-lg border border-white/70 px-3 text-sm font-medium hover:bg-marca-oscura"
                >
                  Carrito
                  <span className="rounded-full bg-white px-2 text-xs font-bold text-marca">{articulos}</span>
                </Link>
              )}
              <button
                type="button"
                onClick={manejarCerrarSesion}
                className="min-h-11 rounded-lg border border-white/70 px-3 text-sm font-medium hover:bg-marca-oscura"
              >
                Cerrar sesión
              </button>
              {enlaces.length > 0 && (
                <button
                  type="button"
                  onClick={() => setMenuAbierto((abierto) => !abierto)}
                  aria-expanded={menuAbierto}
                  aria-controls="menu-principal"
                  className="min-h-11 rounded-lg border border-white/70 px-3 text-sm font-medium hover:bg-marca-oscura sm:hidden"
                >
                  {menuAbierto ? 'Cerrar menú' : 'Menú'}
                </button>
              )}
            </div>
          ) : (
            <Link
              to="/login"
              className="flex min-h-11 items-center rounded-lg border border-white/70 px-3 text-sm font-medium hover:bg-marca-oscura"
            >
              Iniciar sesión
            </Link>
          )}
        </div>
      </header>

      {enlaces.length > 0 && (
        <Navegacion
          enlaces={enlaces}
          abierto={menuAbierto}
          alNavegar={() => setMenuAbierto(false)}
        />
      )}

      {/* HU-40: avisos de pedidos asignados o retirados, en cualquier pantalla del repartidor */}
      {usuario?.rol === ROLES.REPARTIDOR && <AvisosRepartidor />}

      {/* HU-16: alertas de stock bajo para el operador, en cualquier pantalla suya */}
      {usuario?.rol === ROLES.OPERADOR ? (
        <AlertasInventarioProvider>{contenido}</AlertasInventarioProvider>
      ) : (
        contenido
      )}

      <footer className="border-t border-borde px-4 py-4 text-center text-sm text-texto-suave">
        DomiPedidosX · Universidad del Valle · Desarrollo de Software I
      </footer>
    </div>
  )
}
