import { useEffect, useState } from 'react'
import {
  actualizarInsumo,
  eliminarInsumo,
  listarInsumos,
  listarProductosOpciones,
} from '../../api/menu.js'
import { interpretarError } from '../../api/errores.js'
import { UNIDADES } from '../../utils/unidades.js'
import FormularioInsumo from '../../components/menu/FormularioInsumo.jsx'
import IngredientesProducto from '../../components/menu/IngredientesProducto.jsx'
import Alerta from '../../components/ui/Alerta.jsx'
import Boton from '../../components/ui/Boton.jsx'
import Casilla from '../../components/ui/Casilla.jsx'
import Selector from '../../components/ui/Selector.jsx'
import Tarjeta from '../../components/ui/Tarjeta.jsx'

const NOMBRE_UNIDAD = Object.fromEntries(UNIDADES.map((u) => [u.valor, u.etiqueta]))

// HU-77 · Ingredientes de un producto (vista del operador de sede).
export default function Ingredientes() {
  const [insumos, setInsumos] = useState([])
  const [productos, setProductos] = useState([])
  const [cargando, setCargando] = useState(true)
  const [errorCarga, setErrorCarga] = useState(null)
  const [mostrarEliminados, setMostrarEliminados] = useState(false)
  const [recarga, setRecarga] = useState(0)
  const [editando, setEditando] = useState(null)
  const [mensaje, setMensaje] = useState(null)
  const [productoId, setProductoId] = useState('')

  // Catálogo de ingredientes: se recarga al cambiar el filtro o después de guardar.
  useEffect(() => {
    let vigente = true
    listarInsumos({ activo: mostrarEliminados ? 'todos' : true })
      .then((datos) => {
        if (!vigente) return
        setInsumos(datos)
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
  }, [mostrarEliminados, recarga])

  // Productos para el selector: se cargan una sola vez.
  useEffect(() => {
    let vigente = true
    listarProductosOpciones()
      .then((datos) => {
        if (vigente) setProductos(datos)
      })
      .catch((err) => {
        if (vigente) setErrorCarga(interpretarError(err).general)
      })
    return () => {
      vigente = false
    }
  }, [])

  function recargar() {
    setRecarga((valor) => valor + 1)
  }

  function alGuardar(insumo, fueEdicion) {
    setMensaje({
      tipo: 'exito',
      texto: fueEdicion
        ? `Se guardaron los cambios de "${insumo.nombre}". El menú ya muestra la información nueva.`
        : `Se registró el ingrediente "${insumo.nombre}".`,
    })
    setEditando(null)
    recargar()
  }

  async function eliminar(insumo) {
    const confirmado = window.confirm(
      `¿Eliminar el ingrediente "${insumo.nombre}"? Ya no se podrá agregar a productos; los pedidos anteriores no cambian.`,
    )
    if (!confirmado) return
    try {
      await eliminarInsumo(insumo.id)
      if (editando?.id === insumo.id) setEditando(null)
      setMensaje({ tipo: 'exito', texto: `Se eliminó el ingrediente "${insumo.nombre}".` })
      recargar()
    } catch (err) {
      setMensaje({ tipo: 'error', texto: interpretarError(err).general })
    }
  }

  async function restaurar(insumo) {
    try {
      await actualizarInsumo(insumo.id, { activo: true })
      setMensaje({ tipo: 'exito', texto: `Se restauró el ingrediente "${insumo.nombre}".` })
      recargar()
    } catch (err) {
      const { general, campos } = interpretarError(err)
      setMensaje({ tipo: 'error', texto: campos.nombre ?? general })
    }
  }

  const opcionesProducto = productos.map((producto) => ({
    valor: String(producto.id),
    etiqueta: `${producto.nombre} · ${producto.categoria_nombre}`,
  }))

  return (
    <div className="flex flex-col gap-6">
      <header>
        <h1 className="text-2xl font-bold">Ingredientes</h1>
        <p className="text-texto-suave">
          Composición de cada plato. Marca qué ingredientes puede quitar el cliente.
        </p>
      </header>

      {mensaje && <Alerta tipo={mensaje.tipo} titulo={mensaje.texto} />}
      {errorCarga && <Alerta tipo="error" titulo={errorCarga} />}

      <Tarjeta titulo="Ingredientes por producto">
        <Selector
          etiqueta="Producto"
          opciones={opcionesProducto}
          value={productoId}
          onChange={(evento) => setProductoId(evento.target.value)}
          textoVacio="Selecciona un producto"
          className="mb-4 max-w-md"
        />
        {productoId && (
          <IngredientesProducto key={`${productoId}-${recarga}`} productoId={productoId} />
        )}
      </Tarjeta>

      <div className="grid gap-6 lg:grid-cols-[minmax(0,2fr)_minmax(0,3fr)]">
        <Tarjeta>
          <FormularioInsumo
            key={editando?.id ?? 'nuevo'}
            insumo={editando}
            alGuardar={alGuardar}
            alCancelar={() => setEditando(null)}
          />
        </Tarjeta>

        <Tarjeta titulo="Catálogo de ingredientes">
          <Casilla
            etiqueta="Mostrar también los eliminados"
            checked={mostrarEliminados}
            onChange={(evento) => setMostrarEliminados(evento.target.checked)}
            className="mb-4"
          />

          {cargando ? (
            <p className="text-texto-suave">Cargando ingredientes…</p>
          ) : insumos.length === 0 ? (
            <p className="text-texto-suave">Todavía no hay ingredientes registrados.</p>
          ) : (
            <ul className="flex flex-col gap-2">
              {insumos.map((insumo) => (
                <li
                  key={insumo.id}
                  className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-borde bg-fondo px-3 py-2"
                >
                  <div>
                    <p className="font-medium">{insumo.nombre}</p>
                    <p className="text-sm text-texto-suave">
                      {NOMBRE_UNIDAD[insumo.unidad_medida] ?? insumo.unidad_medida}
                    </p>
                    {!insumo.activo && <p className="text-sm text-aviso">Eliminado</p>}
                  </div>
                  <div className="flex gap-2">
                    {insumo.activo ? (
                      <>
                        <Boton
                          variante="secundario"
                          onClick={() => setEditando(insumo)}
                          aria-label={`Editar ${insumo.nombre}`}
                        >
                          Editar
                        </Boton>
                        <Boton
                          variante="peligro"
                          onClick={() => eliminar(insumo)}
                          aria-label={`Eliminar ${insumo.nombre}`}
                        >
                          Eliminar
                        </Boton>
                      </>
                    ) : (
                      <Boton
                        variante="secundario"
                        onClick={() => restaurar(insumo)}
                        aria-label={`Restaurar ${insumo.nombre}`}
                      >
                        Restaurar
                      </Boton>
                    )}
                  </div>
                </li>
              ))}
            </ul>
          )}
        </Tarjeta>
      </div>
    </div>
  )
}
