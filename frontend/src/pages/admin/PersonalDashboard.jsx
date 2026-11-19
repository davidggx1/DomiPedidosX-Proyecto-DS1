import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { listarEmpleados } from '../../api/usuarios.js'
import Boton from '../../components/ui/Boton.jsx'
import Alerta from '../../components/ui/Alerta.jsx'
import { claseEstadoCuenta, textoSede } from '../../utils/personal.js'

export default function PersonalDashboard() {
  const [empleados, setEmpleados] = useState([])
  const [busqueda, setBusqueda] = useState('')
  const [filtroRol, setFiltroRol] = useState('TODOS')
  const [filtroEstado, setFiltroEstado] = useState('TODOS')
  const [cargando, setCargando] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    let activo = true
    listarEmpleados()
      .then((data) => {
        if (activo) {
          const lista = Array.isArray(data) ? data : data?.results || []
          setEmpleados(lista)
          setCargando(false)
        }
      })
      .catch((err) => {
        if (activo) {
          console.error('Error al cargar empleados:', err)
          setError('No se pudo obtener el listado de empleados.')
          setCargando(false)
        }
      })

    return () => {
      activo = false
    }
  }, [])

  const empleadosFiltrados = empleados.filter((emp) => {
    const coincideNombre = `${emp.nombres} ${emp.apellidos} ${emp.usuario?.email || emp.email}`
      .toLowerCase()
      .includes(busqueda.toLowerCase())

    const coincideRol =
      filtroRol === 'TODOS' || (emp.rol || emp.grupo_nombre)?.toUpperCase() === filtroRol

    const coincideEstado =
      filtroEstado === 'TODOS' || (filtroEstado === 'ACTIVAS') === Boolean(emp.is_active)

    return coincideNombre && coincideRol && coincideEstado
  })

  return (
    <div className="space-y-6">
      {/* Encabezado y Acción Principal */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold">Gestión de Personal</h1>
          <p className="text-sm text-texto-suave">
            Administra las cuentas del equipo operativo y sus sedes asignadas.
          </p>
        </div>
        <Link to="/admin/personal/nuevo">
          <Boton variante="primario">+ Registrar Nuevo Empleado</Boton>
        </Link>
      </div>

      {error && <Alerta tipo="error" titulo={error} />}

      {/* Filtros de Búsqueda */}
      <div className="grid grid-cols-1 gap-4 rounded-xl border border-borde bg-superficie p-4 md:grid-cols-4">
        <div className="md:col-span-2">
          <label className="block text-xs font-semibold uppercase mb-1">Buscar</label>
          <input
            type="text"
            placeholder="Buscar por nombre, apellido o correo..."
            value={busqueda}
            onChange={(e) => setBusqueda(e.target.value)}
            className="w-full rounded-lg border border-borde bg-fondo p-2.5 text-sm text-texto"
          />
        </div>
        <div>
          <label className="block text-xs font-semibold uppercase mb-1">Filtrar por Rol</label>
          <select
            value={filtroRol}
            onChange={(e) => setFiltroRol(e.target.value)}
            className="w-full rounded-lg border border-borde bg-fondo p-2.5 text-sm text-texto"
          >
            <option value="TODOS">Todos los roles</option>
            <option value="OPERADOR">Operador</option>
            <option value="COCINA">Cocina</option>
            <option value="REPARTIDOR">Repartidor</option>
            <option value="ADMINISTRADOR">Administrador</option>
          </select>
        </div>
        <div>
          <label className="block text-xs font-semibold uppercase mb-1">Estado</label>
          <select
            value={filtroEstado}
            onChange={(e) => setFiltroEstado(e.target.value)}
            className="w-full rounded-lg border border-borde bg-fondo p-2.5 text-sm text-texto"
          >
            <option value="TODOS">Todas</option>
            <option value="ACTIVAS">Activas</option>
            <option value="DESACTIVADAS">Desactivadas</option>
          </select>
        </div>
      </div>

      {/* Tabla de Empleados */}
      <div className="overflow-x-auto rounded-xl border border-borde bg-superficie shadow-sm">
        {cargando ? (
          <div className="p-8 text-center text-texto-suave">Cargando personal...</div>
        ) : empleadosFiltrados.length === 0 ? (
          <div className="p-8 text-center text-texto-suave">
            No se encontraron empleados registrados.
          </div>
        ) : (
          <table className="w-full text-left text-sm">
            <thead className="border-b border-borde bg-fondo text-xs uppercase text-texto-suave">
              <tr>
                <th className="px-4 py-3">Empleado</th>
                <th className="px-4 py-3">Documento</th>
                <th className="px-4 py-3">Contacto</th>
                <th className="px-4 py-3">Rol</th>
                <th className="px-4 py-3">Sede</th>
                <th className="px-4 py-3">Estado</th>
                <th className="px-4 py-3">Acciones</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-borde">
              {empleadosFiltrados.map((emp) => (
                <tr key={emp.id} className="hover:bg-superficie-alta">
                  <td className="px-4 py-3 font-medium">
                    <div>
                      {emp.nombres} {emp.apellidos}
                    </div>
                    <div className="text-xs text-texto-suave">
                      {emp.usuario?.email || emp.email}
                    </div>
                  </td>
                  <td className="px-4 py-3">
                    <span className="text-xs font-semibold">{emp.tipo_documento}</span>{' '}
                    {emp.num_documento}
                  </td>
                  <td className="px-4 py-3">{emp.celular}</td>
                  <td className="px-4 py-3">
                    <span className="inline-block rounded-full bg-marca/10 px-2.5 py-0.5 text-xs font-semibold text-marca uppercase">
                      {emp.rol || emp.grupo_nombre}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    {textoSede(emp) || (
                      <span className="text-texto-suave italic">Sin Sede (Admin)</span>
                    )}
                  </td>
                  <td className="px-4 py-3">
                    <span
                      className={`rounded-full border px-2 py-0.5 text-xs font-medium ${claseEstadoCuenta(
                        emp.is_active,
                      )}`}
                    >
                      {emp.is_active ? 'Activa' : 'Desactivada'}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    <Link
                      to={`/admin/personal/${emp.id}/editar`}
                      className="text-marca-clara underline underline-offset-4"
                      aria-label={`Editar a ${emp.nombres} ${emp.apellidos}`}
                    >
                      {emp.is_active ? 'Editar' : 'Editar / reactivar'}
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  )
}