import { useCallback, useEffect, useState } from 'react'
import {
  eliminarProducto,
  listarCategorias,
  listarProductos,
  listarSedesMenu,
} from '../../api/menu.js'
import { interpretarError } from '../../api/errores.js'
import { formatearPrecio } from '../../utils/formato.js'
import DisponibilidadProducto from '../../components/menu/DisponibilidadProducto.jsx'
import FormularioProducto from '../../components/menu/FormularioProducto.jsx'
import Alerta from '../../components/ui/Alerta.jsx'
import Boton from '../../components/ui/Boton.jsx'
import Modal from '../../components/ui/Modal.jsx'
import Selector from '../../components/ui/Selector.jsx'
import Tarjeta from '../../components/ui/Tarjeta.jsx'

// HU-11 · Productos del menú (vista del operador de sede).
export default function Productos() {
  const [productos, setProductos] = useState([])
  const [categorias, setCategorias] = useState([])
  const [sedes, setSedes] = useState([])
  const [cargando, setCargando] = useState(true)
  const [errorCarga, setErrorCarga] = useState(null)
  const [filtroCategoria, setFiltroCategoria] = useState('')
  const [recarga, setRecarga] = useState(0)
  const [editando, setEditando] = useState(null)
  const [mensaje, setMensaje] = useState(null)
  const [conDisponibilidad, setConDisponibilidad] = useState(null)
  const [porEliminar, setPorEliminar] = useState(null) // HU-79: product in the confirmation modal
  const [eliminando, setEliminando] = useState(false)
  const [errorEliminar, setErrorEliminar] = useState(null)

  // Listado: se recarga al cambiar el filtro o después de guardar.
  useEffect(() => {
    let vigente = true
    listarProductos({ categoria: filtroCategoria || undefined })
      .then((datos) => {
        if (!vigente) return
        setProductos(datos)
        setErrorCarga(null)
      })
      .catch((err) => {
        if (vigente) setErrorCarga(interpretarError(err).general)
      })
      .finally(() => {
        if (vigente) setCargando(false)
      })
    return () => {
      vigente = false
    }
  }, [filtroCategoria, recarga])

  // Categorías y sedes para el formulario: se cargan una sola vez.
  useEffect(() => {
    let vigente = true
    Promise.all([listarCategorias(), listarSedesMenu()])
      .then(([listaCategorias, listaSedes]) => {
        if (!vigente) return
        setCategorias(listaCategorias)
        setSedes(listaSedes)
      })
      .catch((err) => {
        if (vigente) setErrorCarga(interpretarError(err).general)
      })
    return () => {
      vigente = false
    }
  }, [])

  function alGuardar(producto, fueEdicion) {
    setMensaje({
      tipo: 'exito',
      texto: fueEdicion
        ? `Se guardaron los cambios de "${producto.nombre}". Los clientes ya ven la versión nueva; los pedidos anteriores conservan su precio.`
        : `Se creó el producto "${producto.nombre}".`,
    })
    setEditando(null)
    setRecarga((valor) => valor + 1)
  }

  const cerrarModal = useCallback(() => {
    setPorEliminar(null)
    setErrorEliminar(null)
  }, [])

  function pedirEliminar(producto) {
    setMensaje(null)
    setErrorEliminar(null)
    setPorEliminar(producto)
  }

  // HU-79: soft delete, the product stays as inactive and old orders keep it
  async function eliminar() {
    setEliminando(true)
    setErrorEliminar(null)
    try {
      await eliminarProducto(porEliminar.id)
      setMensaje({
        tipo: 'exito',
        texto: `Se eliminó "${porEliminar.nombre}" del menú. Los pedidos anteriores lo conservan.`,
      })
      if (editando?.id === porEliminar.id) setEditando(null)
      setPorEliminar(null)
      setRecarga((valor) => valor + 1)
    } catch (error) {
      setErrorEliminar(interpretarError(error).general)
    } finally {
      setEliminando(false)
    }
  }

  function empezarEdicion(producto) {
    setEditando(producto)
    setMensaje(null)
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }

  const nombreSede = Object.fromEntries(sedes.map((sede) => [sede.id, sede.nombre]))
  const opcionesFiltro = categorias.map((categoria) => ({
    valor: String(categoria.id),
    etiqueta: categoria.nombre,
  }))

  return (
    <div className="flex flex-col gap-6">
      <header>
        <h1 className="text-2xl font-bold">Productos del menú</h1>
        <p className="text-texto-suave">
          Crea y edita los productos que ven los clientes: foto, precio, tiempo de preparación,
          categoría y sedes donde se ofrecen.
        </p>
      </header>

      {mensaje && <Alerta tipo={mensaje.tipo} titulo={mensaje.texto} />}
      {errorCarga && <Alerta tipo="error" titulo={errorCarga} />}

      <div className="grid gap-6 lg:grid-cols-[minmax(0,2fr)_minmax(0,3fr)]">
        <Tarjeta className="self-start">
          <FormularioProducto
            key={editando?.id ?? 'nuevo'}
            producto={editando}
            categorias={categorias}
            sedes={sedes}
            alGuardar={alGuardar}
            alCancelar={() => setEditando(null)}
          />
        </Tarjeta>

        <Tarjeta titulo="Listado de productos">
          <Selector
            etiqueta="Filtrar por categoría"
            opciones={opcionesFiltro}
            value={filtroCategoria}
            onChange={(evento) => setFiltroCategoria(evento.target.value)}
            textoVacio="Todas las categorías"
            className="mb-4 max-w-sm"
          />

          {cargando ? (
            <p className="text-texto-suave">Cargando productos…</p>
          ) : productos.length === 0 ? (
            <p className="text-texto-suave">
              {filtroCategoria
                ? 'No hay productos en esta categoría.'
                : 'Todavía no hay productos registrados.'}
            </p>
          ) : (
            <ul className="flex flex-col gap-3">
              {productos.map((producto) => (
                <li
                  key={producto.id}
                  className={`flex flex-col gap-3 rounded-lg border bg-fondo p-3 sm:flex-row sm:flex-wrap sm:items-center ${
                    editando?.id === producto.id ? 'border-marca' : 'border-borde'
                  }`}
                >
                  {producto.imagen ? (
                    <img
                      src={producto.imagen}
                      alt={`Foto de ${producto.nombre}`}
                      className="aspect-video w-full rounded-md object-cover sm:w-28 sm:shrink-0"
                    />
                  ) : (
                    <div
                      aria-hidden="true"
                      className="aspect-video w-full rounded-md bg-superficie-alta sm:w-28 sm:shrink-0"
                    />
                  )}

                  <div className="flex min-w-0 flex-1 flex-col gap-1">
                    <p className="font-medium">
                      {producto.nombre}{' '}
                      <span className="text-texto-suave">· {formatearPrecio(producto.precio_base)}</span>
                    </p>
                    <p className="text-sm text-texto-suave">
                      {producto.categoria_nombre} · {producto.tiempo_preparacion} min
                    </p>
                    <p className="text-sm text-texto-suave">
                      {producto.sedes.length > 0
                        ? `Sedes: ${producto.sedes.map((id) => nombreSede[id] ?? `#${id}`).join(', ')}`
                        : 'No se ofrece en ninguna sede'}
                    </p>
                    {!producto.activo && <p className="text-sm text-aviso">Inactivo</p>}
                  </div>

                  <div className="flex gap-2 self-start sm:self-center">
                    <Boton
                      variante="secundario"
                      onClick={() => setConDisponibilidad((actual) => (actual === producto.id ? null : producto.id))}
                      aria-expanded={conDisponibilidad === producto.id}
                      aria-controls={`disponibilidad-${producto.id}`}
                      aria-label={`Disponibilidad de ${producto.nombre}`}
                    >
                      Disponibilidad
                    </Boton>
                    <Boton
                      variante="secundario"
                      onClick={() => empezarEdicion(producto)}
                      aria-label={`Editar ${producto.nombre}`}
                    >
                      Editar
                    </Boton>
                    {producto.activo && (
                      <Boton
                        variante="peligro"
                        onClick={() => pedirEliminar(producto)}
                        aria-label={`Eliminar ${producto.nombre}`}
                      >
                        Eliminar
                      </Boton>
                    )}
                  </div>

                  {conDisponibilidad === producto.id && (
                    <div id={`disponibilidad-${producto.id}`} className="basis-full">
                      <DisponibilidadProducto
                        producto={producto}
                        alCambiar={() => setRecarga((valor) => valor + 1)}
                      />
                    </div>
                  )}
                </li>
              ))}
            </ul>
          )}
        </Tarjeta>
      </div>

      {porEliminar && (
        <Modal
          titulo="Eliminar producto"
          alCerrar={cerrarModal}
          acciones={
            <>
              <Boton variante="secundario" onClick={cerrarModal} disabled={eliminando}>
                Cancelar
              </Boton>
              <Boton variante="peligro" onClick={eliminar} cargando={eliminando}>
                Eliminar
              </Boton>
            </>
          }
        >
          <p>
            ¿Eliminar <strong>{porEliminar.nombre}</strong> del menú? Dejará de mostrarse a los
            clientes y se quitará de los carritos que lo tengan.
          </p>
          <p className="mt-2 text-sm text-texto-suave">
            Los pedidos anteriores conservan el producto y su precio.
          </p>
          {errorEliminar && <Alerta tipo="error" titulo={errorEliminar} />}
        </Modal>
      )}
    </div>
  )
}
