import { useState } from 'react'
import { Link, Outlet, useNavigate } from 'react-router-dom'
import AlertasInventarioProvider from '../../alertas/AlertasInventarioProvider.jsx'
import { useAuth } from '../../auth/useAuth.js'
import { ENLACES_POR_ROL, ETIQUETA_ROL, ROLES } from '../../auth/roles.js'
import { useCarrito } from '../../carrito/useCarrito.js'
import AvisosRepartidor from '../repartidor/AvisosRepartidor.jsx'
import BotonTema from './BotonTema.jsx'
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

      <header className="bg-encabezado text-sobre-encabezado shadow-sm">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-3 px-4 py-3">
          <Link to="/" className="flex items-center gap-2 rounded-lg" aria-label="DomiPedidosX, inicio">
            <span
              aria-hidden="true"
              className="flex size-9 items-center justify-center rounded-xl bg-logo font-titulo text-lg font-extrabold text-sobre-logo"
            >
              D
            </span>
            <span className="font-titulo text-lg font-bold sm:text-xl">
              DomiPedidos<span className="text-acento">X</span>
            </span>
          </Link>

          <div className="flex flex-wrap items-center justify-end gap-2 sm:gap-3">
            {usuario && (
              <p className="hidden text-sm sm:block">
                {usuario.nombre}
                <span className="opacity-80"> · {ETIQUETA_ROL[usuario.rol]}</span>
              </p>
            )}
            <BotonTema />
            {usuario ? (
              <>
                {usuario.rol === ROLES.CLIENTE && (
                  <Link
                    to="/carrito"
                    aria-label={`Carrito, ${articulos} ${articulos === 1 ? 'producto' : 'productos'}`}
                    className="flex min-h-11 rounded-full border border-sobre-encabezado/40 px-4 text-sm font-medium transition-colors hover:bg-sobre-encabezado/10 items-center gap-2"
                  >
                    Carrito
                    <span className="rounded-full bg-acento px-2 text-xs font-bold text-sobre-acento">{articulos}</span>
                  </Link>
                )}
                <button type="button" onClick={manejarCerrarSesion} className="min-h-11 rounded-full border border-sobre-encabezado/40 px-4 text-sm font-medium transition-colors hover:bg-sobre-encabezado/10">
                  Cerrar sesión
                </button>
                {enlaces.length > 0 && (
                  <button
                    type="button"
                    onClick={() => setMenuAbierto((abierto) => !abierto)}
                    aria-expanded={menuAbierto}
                    aria-controls="menu-principal"
                    className="min-h-11 rounded-full border border-sobre-encabezado/40 px-4 text-sm font-medium transition-colors hover:bg-sobre-encabezado/10 sm:hidden"
                  >
                    {menuAbierto ? 'Cerrar menú' : 'Menú'}
                  </button>
                )}
              </>
            ) : (
              <Link
                to="/login"
                className="flex min-h-11 items-center rounded-full bg-sobre-encabezado px-4 text-sm font-semibold text-encabezado transition-opacity hover:opacity-90"
              >
                Iniciar sesión
              </Link>
            )}
          </div>
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
