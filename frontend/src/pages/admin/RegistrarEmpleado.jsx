import { useState, useEffect } from 'react'
import { registrarEmpleado } from '../../api/usuarios.js'
import { listarSedesMenu } from '../../api/menu.js'
import Boton from '../../components/ui/Boton.jsx'
import Alerta from '../../components/ui/Alerta.jsx'

export default function RegistrarEmpleado() {
  const [formData, setFormData] = useState({
    email: '',
    password: '',
    nombres: '',
    apellidos: '',
    tipo_documento: 'CC',
    num_documento: '',
    celular: '',
    direccion: '',
    rol: 'OPERADOR',
    sede_id: '',
  })

  const [sedes, setSedes] = useState([])
  const [cargando, setCargando] = useState(false)
  const [mensaje, setMensaje] = useState(null)

  useEffect(() => {
    listarSedesMenu()
      .then((data) => {
        // Asegura extraer la lista si data es { sedes: [...] } o [...]
        const listaSedes = Array.isArray(data) ? data : data?.sedes || []
        setSedes(listaSedes)
      })
      .catch((err) => {
        console.error('Error al cargar sedes:', err)
      })
  }, [])

  const handleChange = (e) => {
    const { name, value } = e.target
    setFormData((prev) => ({ ...prev, [name]: value }))
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    setMensaje(null)

    // Validar manualmente la sede para roles operativos
    if (formData.rol !== 'ADMINISTRADOR' && !formData.sede_id) {
      setMensaje({ tipo: 'error', texto: 'Por favor selecciona una sede obligatoria para el rol seleccionado.' })
      return
    }

    try {
      setCargando(true)
      const payload = {
        ...formData,
        sede_id: formData.rol === 'ADMINISTRADOR' ? null : Number(formData.sede_id),
      }

      const res = await registrarEmpleado(payload)
      setMensaje({
        tipo: 'exito',
        texto: `¡Empleado registrado con éxito! Contraseña inicial: ${res.contrasena_inicial}`,
      })

      // Reiniciar formulario
      setFormData({
        email: '',
        password: '',
        nombres: '',
        apellidos: '',
        tipo_documento: 'CC',
        num_documento: '',
        celular: '',
        direccion: '',
        rol: 'OPERADOR',
        sede_id: '',
      })
    } catch (err) {
      console.error('Error capturado en submit:', err)
      const dataError = err.response?.data
      let textoError = 'Error al registrar el empleado.'
      if (typeof dataError === 'object' && dataError !== null) {
        textoError = Object.entries(dataError)
          .map(([k, v]) => `${k}: ${Array.isArray(v) ? v.join(', ') : v}`)
          .join(' | ')
      } else if (err.message) {
        textoError = err.message
      }
      setMensaje({ tipo: 'error', texto: textoError })
    } finally {
      setCargando(false)
    }
  }

  return (
    <div className="mx-auto max-w-2xl rounded-xl border border-borde bg-superficie p-6 shadow-sm">
      <h1 className="mb-6 text-2xl font-bold">Registrar Nuevo Empleado (HU-08)</h1>

      {mensaje && <Alerta tipo={mensaje.tipo} titulo={mensaje.texto} />}

      <form onSubmit={handleSubmit} className="space-y-4">
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
          <div>
            <label className="block text-sm font-medium mb-1">Nombres</label>
            <input
              type="text"
              name="nombres"
              required
              value={formData.nombres}
              onChange={handleChange}
              className="w-full rounded-lg border border-borde bg-fondo p-2.5 text-texto"
            />
          </div>
          <div>
            <label className="block text-sm font-medium mb-1">Apellidos</label>
            <input
              type="text"
              name="apellidos"
              required
              value={formData.apellidos}
              onChange={handleChange}
              className="w-full rounded-lg border border-borde bg-fondo p-2.5 text-texto"
            />
          </div>
        </div>

        <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
          <div>
            <label className="block text-sm font-medium mb-1">Correo Electrónico</label>
            <input
              type="email"
              name="email"
              required
              value={formData.email}
              onChange={handleChange}
              className="w-full rounded-lg border border-borde bg-fondo p-2.5 text-texto"
            />
          </div>
          <div>
            <label className="block text-sm font-medium mb-1">Contraseña (Opcional)</label>
            <input
              type="password"
              name="password"
              placeholder="Autogenerada si se deja vacío"
              value={formData.password}
              onChange={handleChange}
              className="w-full rounded-lg border border-borde bg-fondo p-2.5 text-texto"
            />
          </div>
        </div>

        <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
          <div>
            <label className="block text-sm font-medium mb-1">Tipo Doc.</label>
            <select
              name="tipo_documento"
              value={formData.tipo_documento}
              onChange={handleChange}
              className="w-full rounded-lg border border-borde bg-fondo p-2.5 text-texto"
            >
              <option value="CC">Cédula de Ciudadanía</option>
              <option value="CE">Cédula de Extranjería</option>
              <option value="PASAPORTE">Pasaporte</option>
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium mb-1">N° Documento</label>
            <input
              type="text"
              name="num_documento"
              required
              value={formData.num_documento}
              onChange={handleChange}
              className="w-full rounded-lg border border-borde bg-fondo p-2.5 text-texto"
            />
          </div>
          <div>
            <label className="block text-sm font-medium mb-1">Celular</label>
            <input
              type="text"
              name="celular"
              required
              maxLength={10}
              value={formData.celular}
              onChange={handleChange}
              className="w-full rounded-lg border border-borde bg-fondo p-2.5 text-texto"
            />
          </div>
        </div>

        <div>
          <label className="block text-sm font-medium mb-1">Dirección</label>
          <input
            type="text"
            name="direccion"
            required
            value={formData.direccion}
            onChange={handleChange}
            className="w-full rounded-lg border border-borde bg-fondo p-2.5 text-texto"
          />
        </div>

        <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
          <div>
            <label className="block text-sm font-medium mb-1">Rol</label>
            <select
              name="rol"
              value={formData.rol}
              onChange={handleChange}
              className="w-full rounded-lg border border-borde bg-fondo p-2.5 text-texto"
            >
              <option value="OPERADOR">Operador</option>
              <option value="COCINA">Cocina</option>
              <option value="REPARTIDOR">Repartidor</option>
              <option value="ADMINISTRADOR">Administrador</option>
            </select>
          </div>

          {formData.rol !== 'ADMINISTRADOR' && (
            <div>
              <label className="block text-sm font-medium mb-1">Sede Asignada</label>
              <select
                name="sede_id"
                value={formData.sede_id}
                onChange={handleChange}
                className="w-full rounded-lg border border-borde bg-fondo p-2.5 text-texto"
              >
                <option value="">Selecciona una sede...</option>
                {sedes.map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.nombre}
                  </option>
                ))}
              </select>
            </div>
          )}
        </div>

        <Boton tipo="submit" variante="primario" className="w-full mt-4" disabled={cargando}>
          {cargando ? 'Registrando...' : 'Registrar Empleado'}
        </Boton>
      </form>
    </div>
  )
}