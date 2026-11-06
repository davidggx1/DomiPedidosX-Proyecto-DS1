import { Route, Routes } from 'react-router-dom'
import { ROLES } from './auth/roles.js'
import RutaProtegida from './auth/RutaProtegida.jsx'
import Layout from './components/layout/Layout.jsx'
import Carrito from './pages/cliente/Carrito.jsx'
import CategoriasMenu from './pages/CategoriasMenu.jsx'
import EnConstruccion from './pages/EnConstruccion.jsx'
import GuiaEstilo from './pages/GuiaEstilo.jsx'
import Inicio from './pages/Inicio.jsx'
import Login from './pages/Login.jsx'
import NoAutorizado from './pages/NoAutorizado.jsx'
import NoEncontrada from './pages/NoEncontrada.jsx'
import Adiciones from './pages/operador/Adiciones.jsx'
import Ingredientes from './pages/operador/Ingredientes.jsx'
import Inventario from './pages/operador/Inventario.jsx'
import Productos from './pages/operador/Productos.jsx'
import Direcciones from './pages/cliente/Direcciones.jsx'
import Menu from './pages/cliente/Menu.jsx'
import Cuentas from './pages/admin/Cuentas.jsx'

// Rutas de la aplicación. Cada grupo protegido solo deja entrar a su rol.
// Al implementar una HU, reemplaza <EnConstruccion> por la página real.
export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<Inicio />} />
        <Route path="login" element={<Login />} />
        <Route path="guia-estilo" element={<GuiaEstilo />} />
        <Route path="no-autorizado" element={<NoAutorizado />} />

        <Route element={<RutaProtegida roles={[ROLES.CLIENTE]} />}>
          <Route path="menu" element={<Menu />} />
          <Route path="direcciones" element={<Direcciones />} />
          <Route path="mis-pedidos" element={<EnConstruccion titulo="Mis pedidos" historias="HU-26, HU-47" />} />
          <Route path="perfil" element={<EnConstruccion titulo="Mi perfil" historias="HU-07" />} />
          <Route path="carrito" element={<Carrito />} />
        </Route>

        <Route element={<RutaProtegida roles={[ROLES.OPERADOR]} />}>
          <Route path="operador" element={<EnConstruccion titulo="Pedidos entrantes" historias="HU-27, HU-28" />} />
          <Route path="operador/menu" element={<CategoriasMenu />} />
          <Route path="operador/productos" element={<Productos />} />
          <Route path="operador/adiciones" element={<Adiciones />} />
          <Route path="operador/ingredientes" element={<Ingredientes />} />
          <Route path="operador/inventario" element={<Inventario />} />
          <Route path="operador/repartidores" element={<EnConstruccion titulo="Repartidores" historias="HU-35" />} />
        </Route>

        <Route element={<RutaProtegida roles={[ROLES.COCINA]} />}>
          <Route path="cocina" element={<EnConstruccion titulo="Tablero de cocina" historias="HU-29, HU-30, HU-31" />} />
        </Route>

        <Route element={<RutaProtegida roles={[ROLES.REPARTIDOR]} />}>
          <Route path="repartidor" element={<EnConstruccion titulo="Mis entregas" historias="HU-41, HU-42, HU-43, HU-45" />} />
        </Route>

        <Route element={<RutaProtegida roles={[ROLES.ADMINISTRADOR]} />}>
          <Route path="admin" element={<EnConstruccion titulo="Dashboard" historias="HU-70" />} />
          <Route path="admin/pedidos" element={<EnConstruccion titulo="Pedidos del día" historias="HU-67" />} />
          <Route path="admin/sedes" element={<EnConstruccion titulo="Sedes" historias="HU-81, HU-82" />} />
          <Route path="admin/personal" element={<EnConstruccion titulo="Personal" historias="HU-08" />} />
          <Route path="admin/cuentas" element={<Cuentas />} />
        </Route>

        <Route path="*" element={<NoEncontrada />} />
      </Route>
    </Routes>
  )
}
