import { useId, useState } from 'react'
import { actualizarProducto, crearProducto } from '../../api/menu.js'
import { interpretarError } from '../../api/errores.js'
import Alerta from '../ui/Alerta.jsx'
import Boton from '../ui/Boton.jsx'
import CampoTexto from '../ui/CampoTexto.jsx'
import Casilla from '../ui/Casilla.jsx'
import Selector from '../ui/Selector.jsx'
import SelectorImagen from './SelectorImagen.jsx'

const VACIO = {
  nombre: '',
  descripcion: '',
  precio_base: '',
  tiempo_preparacion: '',
  categoria: '',
  sedes: [],
  activo: true,
}

function valoresIniciales(producto) {
  if (!producto) return VACIO
  return {
    nombre: producto.nombre,
    descripcion: producto.descripcion ?? '',
    precio_base: String(Number(producto.precio_base)),
    tiempo_preparacion: String(producto.tiempo_preparacion),
    categoria: String(producto.categoria),
    sedes: producto.sedes.map(String),
    activo: producto.activo,
  }
}

function mismasSedes(a, b) {
  return a.length === b.length && a.every((id) => b.includes(id))
}

// Mismas reglas que el backend, para avisar antes de enviar.
function validar(valores) {
  const errores = {}
  if (!valores.nombre.trim()) errores.nombre = 'El nombre es obligatorio.'

  const precio = Number(valores.precio_base)
  if (valores.precio_base === '') errores.precio_base = 'El precio es obligatorio.'
  else if (Number.isNaN(precio)) errores.precio_base = 'Escribe un precio válido.'
  else if (precio <= 0) errores.precio_base = 'El precio debe ser mayor que 0.'

  const tiempo = Number(valores.tiempo_preparacion)
  if (valores.tiempo_preparacion === '') {
    errores.tiempo_preparacion = 'El tiempo de preparación es obligatorio.'
  } else if (!Number.isInteger(tiempo)) {
    errores.tiempo_preparacion = 'Escribe los minutos como un número entero.'
  } else if (tiempo <= 0) {
    errores.tiempo_preparacion = 'El tiempo de preparación debe ser mayor que 0.'
  }

  if (!valores.categoria) errores.categoria = 'Selecciona una categoría.'
  if (valores.sedes.length === 0) errores.sedes = 'Selecciona al menos una sede.'
  return errores
}

// Formulario para crear o editar un producto del menú (HU-11).
// Si recibe `producto`, edita; si no, crea uno nuevo.
// El padre debe darle una `key` distinta al cambiar de producto para reiniciarlo.
export default function FormularioProducto({ producto, categorias, sedes, alGuardar, alCancelar }) {
  const esEdicion = Boolean(producto)
  const idDescripcion = useId()
  const idSedes = useId()
  const [valores, setValores] = useState(() => valoresIniciales(producto))
  const [archivo, setArchivo] = useState(null)
  const [errores, setErrores] = useState({})
  const [errorGeneral, setErrorGeneral] = useState(null)
  const [guardando, setGuardando] = useState(false)

  // En edición se permite conservar la categoría actual aunque ya esté inactiva.
  const opcionesCategoria = categorias
    .filter((categoria) => categoria.activa || String(categoria.id) === valores.categoria)
    .map((categoria) => ({
      valor: String(categoria.id),
      etiqueta: categoria.activa ? categoria.nombre : `${categoria.nombre} (inactiva)`,
    }))

  function cambiar(evento) {
    const { name, value, type, checked } = evento.target
    setValores((actuales) => ({ ...actuales, [name]: type === 'checkbox' ? checked : value }))
  }

  function alternarSede(id) {
    setValores((actuales) => ({
      ...actuales,
      sedes: actuales.sedes.includes(id)
        ? actuales.sedes.filter((sede) => sede !== id)
        : [...actuales.sedes, id],
    }))
  }

  function cambiarImagen(elegido, problema) {
    setArchivo(elegido)
    setErrores((actuales) => ({ ...actuales, imagen: problema ?? undefined }))
  }

  function armarFormulario() {
    const datos = new FormData()
    datos.append('nombre', valores.nombre.trim())
    datos.append('descripcion', valores.descripcion.trim())
    datos.append('precio_base', valores.precio_base)
    datos.append('tiempo_preparacion', valores.tiempo_preparacion)
    datos.append('categoria', valores.categoria)
    if (esEdicion) datos.append('activo', String(valores.activo))
    if (archivo) datos.append('imagen', archivo)
    // En edición solo se envían las sedes si cambiaron, para no tocar la disponibilidad actual.
    const sedesIniciales = producto?.sedes.map(String) ?? []
    if (!esEdicion || !mismasSedes(valores.sedes, sedesIniciales)) {
      valores.sedes.forEach((id) => datos.append('sedes', id))
    }
    return datos
  }

  async function enviar(evento) {
    evento.preventDefault()
    const nuevosErrores = validar(valores)
    if (errores.imagen) nuevosErrores.imagen = errores.imagen
    setErrores(nuevosErrores)
    setErrorGeneral(null)
    if (Object.keys(nuevosErrores).length > 0) return

    setGuardando(true)
    try {
      const datos = armarFormulario()
      const guardado = esEdicion
        ? await actualizarProducto(producto.id, datos)
        : await crearProducto(datos)
      if (!esEdicion) {
        setValores(VACIO)
        setArchivo(null)
      }
      alGuardar(guardado, esEdicion)
    } catch (error) {
      const { general, campos } = interpretarError(error)
      setErrorGeneral(general)
      setErrores(campos)
    } finally {
      setGuardando(false)
    }
  }

  return (
    <form noValidate onSubmit={enviar} className="flex flex-col gap-4">
      <h2 className="text-lg font-bold">
        {esEdicion ? `Editar "${producto.nombre}"` : 'Nuevo producto'}
      </h2>

      {errorGeneral && <Alerta tipo="error" titulo={errorGeneral} />}

      <SelectorImagen
        archivo={archivo}
        imagenActual={producto?.imagen ?? null}
        error={errores.imagen}
        alCambiar={cambiarImagen}
        nombreProducto={valores.nombre}
      />

      <CampoTexto
        etiqueta="Nombre"
        name="nombre"
        value={valores.nombre}
        onChange={cambiar}
        error={errores.nombre}
        placeholder="Ej.: Hamburguesa clásica"
        maxLength={100}
        requerido
      />

      <div className="flex flex-col gap-1">
        <label htmlFor={idDescripcion} className="text-sm font-medium">
          Descripción
        </label>
        <textarea
          id={idDescripcion}
          name="descripcion"
          rows={3}
          value={valores.descripcion}
          onChange={cambiar}
          placeholder="Opcional. Ej.: Carne de res, queso cheddar y tomate."
          className="rounded-lg border border-borde bg-fondo px-3 py-2 text-texto placeholder:text-texto-suave"
        />
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        <CampoTexto
          etiqueta="Precio (COP)"
          name="precio_base"
          type="number"
          inputMode="decimal"
          min="1"
          step="any"
          value={valores.precio_base}
          onChange={cambiar}
          error={errores.precio_base}
          ayuda="Debe ser mayor que 0."
          requerido
        />
        <CampoTexto
          etiqueta="Tiempo de preparación (min)"
          name="tiempo_preparacion"
          type="number"
          inputMode="numeric"
          min="1"
          step="1"
          value={valores.tiempo_preparacion}
          onChange={cambiar}
          error={errores.tiempo_preparacion}
          ayuda="En minutos, mayor que 0."
          requerido
        />
      </div>

      <Selector
        etiqueta="Categoría"
        name="categoria"
        opciones={opcionesCategoria}
        value={valores.categoria}
        onChange={cambiar}
        error={errores.categoria}
        textoVacio="Selecciona una categoría"
        requerido
      />

      <fieldset
        aria-describedby={errores.sedes ? `${idSedes}-error` : undefined}
        className="flex flex-col gap-2"
      >
        <legend className="mb-1 text-sm font-medium">
          Sedes donde se ofrece
          <span className="text-marca-clara" aria-hidden="true">
            {' '}*
          </span>
        </legend>
        {sedes.length === 0 ? (
          <p className="text-sm text-texto-suave">No hay sedes activas.</p>
        ) : (
          sedes.map((sede) => (
            <Casilla
              key={sede.id}
              etiqueta={sede.nombre}
              checked={valores.sedes.includes(String(sede.id))}
              onChange={() => alternarSede(String(sede.id))}
            />
          ))
        )}
        {errores.sedes && (
          <p id={`${idSedes}-error`} className="text-sm text-error">
            {errores.sedes}
          </p>
        )}
      </fieldset>

      {esEdicion && (
        <Casilla
          etiqueta="Producto activo"
          descripcion="Si lo desactivas, deja de aparecer en el menú del cliente."
          name="activo"
          checked={valores.activo}
          onChange={cambiar}
        />
      )}

      <div className="flex flex-wrap gap-3">
        <Boton tipo="submit" cargando={guardando}>
          {esEdicion ? 'Guardar cambios' : 'Crear producto'}
        </Boton>
        {esEdicion && (
          <Boton variante="secundario" onClick={alCancelar}>
            Cancelar
          </Boton>
        )}
      </div>
    </form>
  )
}
