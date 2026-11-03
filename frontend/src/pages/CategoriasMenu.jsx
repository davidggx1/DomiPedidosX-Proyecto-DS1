import { useEffect, useRef, useState } from 'react'
import api from '../api/cliente.js'
import { interpretarError } from '../api/errores.js'
import Alerta from '../components/ui/Alerta.jsx'
import Boton from '../components/ui/Boton.jsx'
import CampoTexto from '../components/ui/CampoTexto.jsx'
import Casilla from '../components/ui/Casilla.jsx'
import Tarjeta from '../components/ui/Tarjeta.jsx'

const FORMULARIO_VACIO = { nombre: '', descripcion: '', activa: true }
const SIN_ERRORES = { general: null, campos: {} }

function textoProductos(total) {
  return total === 1 ? '1 producto' : `${total} productos`
}

// Category management screen for the operator (HU-10)
export default function CategoriasMenu() {
  const [categorias, setCategorias] = useState([])
  const [cargando, setCargando] = useState(true)
  const [errorCarga, setErrorCarga] = useState(null)

  const [formulario, setFormulario] = useState(FORMULARIO_VACIO)
  const [editando, setEditando] = useState(null) // the category being edited, null = creating
  const [errores, setErrores] = useState(SIN_ERRORES)
  const [exito, setExito] = useState(null)
  const [guardando, setGuardando] = useState(false)
  const campoNombre = useRef(null)

  const [recarga, setRecarga] = useState(0) // bump it to load the list again

  useEffect(() => {
    let activo = true
    api
      .get('/menu/categorias/')
      .then(({ data }) => {
        if (!activo) return
        setCategorias(data)
        setErrorCarga(null)
      })
      .catch((error) => {
        if (activo) setErrorCarga(interpretarError(error).general)
      })
      .finally(() => {
        if (activo) setCargando(false)
      })
    // ignore the answer if the page was closed before it arrived
    return () => {
      activo = false
    }
  }, [recarga])

  function cambiar(evento) {
    const { name, value, type, checked } = evento.target
    setFormulario((actual) => ({ ...actual, [name]: type === 'checkbox' ? checked : value }))
  }

  function empezarEdicion(categoria) {
    setEditando(categoria)
    setFormulario({
      nombre: categoria.nombre,
      descripcion: categoria.descripcion,
      activa: categoria.activa,
    })
    setErrores(SIN_ERRORES)
    setExito(null)
    campoNombre.current?.focus()
  }

  function cancelarEdicion() {
    setEditando(null)
    setFormulario(FORMULARIO_VACIO)
    setErrores(SIN_ERRORES)
  }

  async function guardar(evento) {
    evento.preventDefault()
    setExito(null)

    const nombre = formulario.nombre.trim()
    if (!nombre) {
      setErrores({ general: null, campos: { nombre: 'El nombre de la categoría es obligatorio.' } })
      campoNombre.current?.focus()
      return
    }

    setGuardando(true)
    setErrores(SIN_ERRORES)
    const datos = {
      nombre,
      descripcion: formulario.descripcion.trim(),
      activa: formulario.activa,
    }

    try {
      if (editando) {
        await api.patch(`/menu/categorias/${editando.id}/`, datos)
        setExito(`La categoría "${nombre}" se actualizó correctamente.`)
      } else {
        await api.post('/menu/categorias/', datos)
        setExito(`La categoría "${nombre}" se creó correctamente.`)
      }
      setEditando(null)
      setFormulario(FORMULARIO_VACIO)
      setRecarga((numero) => numero + 1)
    } catch (error) {
      setErrores(interpretarError(error))
    } finally {
      setGuardando(false)
    }
  }

  return (
    <div className="flex flex-col gap-4">
      <h1 className="text-2xl font-bold">Categorías del menú</h1>

      {exito && <Alerta tipo="exito">{exito}</Alerta>}

      <Tarjeta titulo={editando ? `Editar categoría: ${editando.nombre}` : 'Nueva categoría'}>
        <form onSubmit={guardar} noValidate className="flex flex-col gap-4">
          {errores.general && <Alerta tipo="error">{errores.general}</Alerta>}

          {editando && editando.total_productos > 0 && (
            <Alerta tipo="info">
              Cambiar el nombre no afecta a los {textoProductos(editando.total_productos)} de esta
              categoría: siguen en ella.
            </Alerta>
          )}

          <CampoTexto
            ref={campoNombre}
            etiqueta="Nombre"
            name="nombre"
            value={formulario.nombre}
            onChange={cambiar}
            error={errores.campos.nombre}
            maxLength={50}
            requerido
          />
          <CampoTexto
            etiqueta="Descripción"
            name="descripcion"
            value={formulario.descripcion}
            onChange={cambiar}
            error={errores.campos.descripcion}
            ayuda="Opcional."
          />
          <Casilla
            etiqueta="Categoría activa"
            name="activa"
            checked={formulario.activa}
            onChange={cambiar}
          />

          <div className="flex flex-wrap gap-2">
            <Boton tipo="submit" cargando={guardando}>
              {editando ? 'Guardar cambios' : 'Crear categoría'}
            </Boton>
            {editando && (
              <Boton variante="secundario" onClick={cancelarEdicion} disabled={guardando}>
                Cancelar
              </Boton>
            )}
          </div>
        </form>
      </Tarjeta>

      <Tarjeta titulo="Categorías">
        {cargando && <p className="text-texto-suave">Cargando categorías…</p>}

        {errorCarga && <Alerta tipo="error">{errorCarga}</Alerta>}

        {!cargando && !errorCarga && categorias.length === 0 && (
          <p className="text-texto-suave">Aún no hay categorías. Crea la primera con el formulario.</p>
        )}

        {categorias.length > 0 && (
          <ul className="flex flex-col gap-3">
            {categorias.map((categoria) => (
              <li
                key={categoria.id}
                className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-borde bg-fondo p-3"
              >
                <div className="flex min-w-0 flex-col gap-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <h3 className="font-bold">{categoria.nombre}</h3>
                    <span
                      className={`rounded-full border px-2 py-0.5 text-xs font-medium ${
                        categoria.activa ? 'border-exito text-exito' : 'border-aviso text-aviso'
                      }`}
                    >
                      {categoria.activa ? 'Activa' : 'Inactiva'}
                    </span>
                  </div>
                  {categoria.descripcion && (
                    <p className="text-sm text-texto-suave">{categoria.descripcion}</p>
                  )}
                  <p className="text-sm text-texto-suave">{textoProductos(categoria.total_productos)}</p>
                </div>

                <Boton
                  variante="secundario"
                  onClick={() => empezarEdicion(categoria)}
                  aria-label={`Editar la categoría ${categoria.nombre}`}
                >
                  Editar
                </Boton>
              </li>
            ))}
          </ul>
        )}
      </Tarjeta>
    </div>
  )
}
