import { useCallback, useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import api from '../../api/cliente.js'
import Alerta from '../../components/ui/Alerta.jsx'
import Boton from '../../components/ui/Boton.jsx'
import CampoTexto from '../../components/ui/CampoTexto.jsx'
import Casilla from '../../components/ui/Casilla.jsx'
import Selector from '../../components/ui/Selector.jsx'
import Tarjeta from '../../components/ui/Tarjeta.jsx'

export default function Sedes() {
  const navigate = useNavigate()
  const [sedes, setSedes] = useState([])
  const [ciudades, setCiudades] = useState([])
  const [cargando, setCargando] = useState(true)
  const [error, setError] = useState(null)
  const [mensajeExito, setMensajeExito] = useState(null)

  // Estado del Modal de Creación / Edición (HU-81)
  const [modalAbierto, setModalAbierto] = useState(false)
  const [sedeEditando, setSedeEditando] = useState(null)
  const [guardando, setGuardando] = useState(false)
  const [errorForm, setErrorForm] = useState(null)

  // Campos del Formulario
  const [formData, setFormData] = useState({
    nombre: '',
    ciudad: '',
    direccion: '',
    barrio: '',
    telefono: '',
    correo: '',
    latitud: '',
    longitud: '',
    activa: true,
  })

  // Estado para confirmación de desactivación con pedidos pendientes (HU-81)
  const [advertenciaDesactivar, setAdvertenciaDesactivar] = useState(null)

  const cargarDatos = useCallback(async () => {
    setCargando(true)
    setError(null)
    try {
      const [resSedes, resCiudades] = await Promise.all([
        api.get('/sedes/'),
        api.get('/ciudades/').catch(() => ({ data: [] })),
      ])
      setSedes(Array.isArray(resSedes.data) ? resSedes.data : resSedes.data.results ?? [])
      setCiudades(Array.isArray(resCiudades.data) ? resCiudades.data : resCiudades.data.results ?? [])
    } catch {
      setError('No fue posible cargar la lista de sedes.')
    } finally {
      setCargando(false)
    }
  }, [])

  useEffect(() => {
    let activo = true
    Promise.all([
      api.get('/sedes/'),
      api.get('/ciudades/').catch(() => ({ data: [] })),
    ])
      .then(([resSedes, resCiudades]) => {
        if (activo) {
          setSedes(Array.isArray(resSedes.data) ? resSedes.data : resSedes.data.results ?? [])
          setCiudades(Array.isArray(resCiudades.data) ? resCiudades.data : resCiudades.data.results ?? [])
          setCargando(false)
        }
      })
      .catch(() => {
        if (activo) {
          setError('No fue posible cargar la lista de sedes.')
          setCargando(false)
        }
      })
    return () => { activo = false }
  }, [])

  const abrirModalCrear = () => {
    setSedeEditando(null)
    setFormData({
      nombre: '',
      ciudad: ciudades[0]?.id || '',
      direccion: '',
      barrio: '',
      telefono: '',
      correo: '',
      latitud: '0.0',
      longitud: '0.0',
      activa: true,
    })
    setErrorForm(null)
    setModalAbierto(true)
  }

  const abrirModalEditar = (sede) => {
    setSedeEditando(sede)
    setFormData({
      nombre: sede.nombre,
      ciudad: sede.ciudad,
      direccion: sede.direccion,
      barrio: sede.barrio,
      telefono: sede.telefono,
      correo: sede.correo,
      latitud: sede.latitud,
      longitud: sede.longitud,
      activa: sede.activa,
    })
    setErrorForm(null)
    setModalAbierto(true)
  }

  const handleGuardar = async (e) => {
    e.preventDefault()
    setGuardando(true)
    setErrorForm(null)

    try {
      if (sedeEditando) {
        await api.put(`/sedes/${sedeEditando.id}/`, formData)
        setMensajeExito(`Sede "${formData.nombre}" actualizada con éxito.`)
      } else {
        await api.post('/sedes/', formData)
        setMensajeExito(`Sede "${formData.nombre}" creada con éxito.`)
      }
      setModalAbierto(false)
      cargarDatos()
    } catch (err) {
      const msg = err.response?.data?.nombre?.[0] || err.response?.data?.detail || 'Error al guardar los datos de la sede.'
      setErrorForm(msg)
    } finally {
      setGuardando(false)
    }
  }

  const toggleEstadoSede = async (sede, confirmarDesactivacion = false) => {
    setError(null)
    setMensajeExito(null)
    try {
      const nuevoEstado = !sede.activa
      const payload = {
        ...sede,
        activa: nuevoEstado,
        confirmar_desactivacion: confirmarDesactivacion,
      }

      await api.put(`/sedes/${sede.id}/`, payload)
      setAdvertenciaDesactivar(null)
      setMensajeExito(`Sede "${sede.nombre}" ${nuevoEstado ? 'activada' : 'desactivada'} correctamente.`)
      cargarDatos()
    } catch (err) {
      const data = err.response?.data
      if (err.response?.status === 400 && data?.warning) {
        setAdvertenciaDesactivar({
          sede,
          mensaje: data.message,
        })
      } else {
        setError('No fue posible cambiar el estado de la sede.')
      }
    }
  }

  return (
    <div className="flex flex-col gap-6">
      <header className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold">Sedes</h1>
          <p className="text-texto-suave">Administra las sedes operativas y sus horarios de atención.</p>
        </div>
        <Boton onClick={abrirModalCrear}>+ Nueva Sede</Boton>
      </header>

      {error && <Alerta tipo="error" titulo={error} />}
      {mensajeExito && <Alerta tipo="exito" titulo={mensajeExito} />}

      {cargando ? (
        <p className="text-texto-suave">Cargando sedes…</p>
      ) : sedes.length === 0 ? (
        <Tarjeta>
          <p className="text-texto-suave">No hay sedes registradas aún.</p>
        </Tarjeta>
      ) : (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {sedes.map((sede) => (
            <Tarjeta key={sede.id} className="flex flex-col justify-between gap-4">
              <div>
                <div className="flex items-center justify-between gap-2 mb-2">
                  <h3 className="text-lg font-bold">{sede.nombre}</h3>
                  <span
                    className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${
                      sede.activa
                        ? 'bg-verde/10 text-verde border border-verde/30'
                        : 'bg-rojo/10 text-rojo border border-rojo/30'
                    }`}
                  >
                    {sede.activa ? 'Activa' : 'Inactiva'}
                  </span>
                </div>
                <p className="text-sm text-texto-suave">{sede.direccion} - {sede.barrio}</p>
                <p className="text-xs text-texto-suave mt-1">Ciudad: {sede.ciudad_nombre || sede.ciudad}</p>
                <p className="text-xs text-texto-suave">Tel: {sede.telefono}</p>
              </div>

              <div className="flex flex-col gap-2 pt-2 border-t border-borde">
                <Boton
                  variante="secundario"
                  className="w-full text-xs"
                  onClick={() => navigate(`/admin/horarios?sede=${sede.id}`)}
                >
                  📅 Horarios y Festivos
                </Boton>

                <div className="flex gap-2">
                  <Boton
                    variante="fantasma"
                    className="flex-1 text-xs"
                    onClick={() => abrirModalEditar(sede)}
                  >
                    Editar
                  </Boton>
                  <Boton
                    variante={sede.activa ? 'peligro' : 'secundario'}
                    className="flex-1 text-xs"
                    onClick={() => toggleEstadoSede(sede)}
                  >
                    {sede.activa ? 'Desactivar' : 'Activar'}
                  </Boton>
                </div>
              </div>
            </Tarjeta>
          ))}
        </div>
      )}

      {advertenciaDesactivar && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-negro/50 p-4">
          <div className="w-full max-w-md rounded-xl border border-borde bg-superficie p-6 shadow-lg">
            <h3 className="text-lg font-bold text-aviso">⚠️ Advertencia de Desactivación</h3>
            <p className="mt-2 text-sm text-texto">{advertenciaDesactivar.mensaje}</p>

            <div className="mt-6 flex justify-end gap-3">
              <Boton variante="secundario" onClick={() => setAdvertenciaDesactivar(null)}>
                Cancelar
              </Boton>
              <Boton
                variante="peligro"
                onClick={() => toggleEstadoSede(advertenciaDesactivar.sede, true)}
              >
                Sí, desactivar de todos modos
              </Boton>
            </div>
          </div>
        </div>
      )}

      {modalAbierto && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-negro/50 p-4 overflow-y-auto">
          <div className="w-full max-w-lg rounded-xl border border-borde bg-superficie p-6 shadow-lg my-8">
            <h3 className="text-lg font-bold">
              {sedeEditando ? 'Editar Sede' : 'Crear Nueva Sede'}
            </h3>

            {errorForm && <Alerta tipo="error" titulo={errorForm} className="mt-3" />}

            <form onSubmit={handleGuardar} className="mt-4 flex flex-col gap-4">
              <CampoTexto
                etiqueta="Nombre de la Sede"
                value={formData.nombre}
                onChange={(e) => setFormData({ ...formData, nombre: e.target.value })}
                requerido
              />

              {ciudades.length > 0 ? (
                <Selector
                  etiqueta="Ciudad"
                  opciones={ciudades.map((c) => ({ valor: c.id, etiqueta: c.nombre }))}
                  value={formData.ciudad}
                  onChange={(e) => setFormData({ ...formData, ciudad: e.target.value })}
                  requerido
                />
              ) : (
                <CampoTexto
                  etiqueta="ID o Nombre de Ciudad"
                  value={formData.ciudad}
                  onChange={(e) => setFormData({ ...formData, ciudad: e.target.value })}
                  requerido
                />
              )}

              <CampoTexto
                etiqueta="Dirección"
                value={formData.direccion}
                onChange={(e) => setFormData({ ...formData, direccion: e.target.value })}
                requerido
              />

              <div className="grid grid-cols-2 gap-3">
                <CampoTexto
                  etiqueta="Barrio"
                  value={formData.barrio}
                  onChange={(e) => setFormData({ ...formData, barrio: e.target.value })}
                  requerido
                />
                <CampoTexto
                  etiqueta="Teléfono"
                  value={formData.telefono}
                  onChange={(e) => setFormData({ ...formData, telefono: e.target.value })}
                  requerido
                />
              </div>

              <CampoTexto
                tipo="email"
                etiqueta="Correo de contacto"
                value={formData.correo}
                onChange={(e) => setFormData({ ...formData, correo: e.target.value })}
                requerido
              />

              <Casilla
                etiqueta="Sede Activa"
                descripcion="Permite recibir pedidos en esta sede"
                checked={formData.activa}
                onChange={(e) => setFormData({ ...formData, activa: e.target.checked })}
              />

              <div className="mt-4 flex justify-end gap-3">
                <Boton
                  variante="secundario"
                  type="button"
                  onClick={() => setModalAbierto(false)}
                  disabled={guardando}
                >
                  Cancelar
                </Boton>
                <Boton tipo="submit" cargando={guardando}>
                  {sedeEditando ? 'Actualizar Sede' : 'Guardar Sede'}
                </Boton>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}