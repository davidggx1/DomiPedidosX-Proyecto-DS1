import { useEffect, useState } from 'react'
import {
  actualizarIngrediente,
  agregarIngrediente,
  listarIngredientesProducto,
  listarInsumos,
  quitarIngrediente,
} from '../../api/menu.js'
import { interpretarError } from '../../api/errores.js'
import { abreviaturaUnidad, formatearCantidad } from '../../utils/unidades.js'
import Alerta from '../ui/Alerta.jsx'
import Boton from '../ui/Boton.jsx'
import CampoTexto from '../ui/CampoTexto.jsx'
import Casilla from '../ui/Casilla.jsx'
import Selector from '../ui/Selector.jsx'

// Sección "Ingredientes" de un producto (HU-77): lista los ingredientes y permite
// marcar cuáles puede quitar el cliente. Pensada para reutilizarse dentro del
// formulario de producto (HU-11), por eso no usa <form>.
export default function IngredientesProducto({ productoId }) {
  const [ingredientes, setIngredientes] = useState([])
  const [catalogo, setCatalogo] = useState([])
  const [cargando, setCargando] = useState(true)
  const [error, setError] = useState(null)
  const [seleccion, setSeleccion] = useState('')
  const [cantidad, setCantidad] = useState('1')
  const [excluible, setExcluible] = useState(false)
  const [errores, setErrores] = useState({})
  const [guardando, setGuardando] = useState(false)
  const [actualizando, setActualizando] = useState(null)
  const [recarga, setRecarga] = useState(0)

  useEffect(() => {
    let vigente = true
    Promise.all([listarIngredientesProducto(productoId), listarInsumos()])
      .then(([delProducto, activos]) => {
        if (!vigente) return
        setIngredientes(delProducto)
        setCatalogo(activos)
        setError(null)
      })
      .catch((err) => {
        if (vigente) setError(interpretarError(err).general)
      })
      .finally(() => {
        if (vigente) setCargando(false)
      })
    return () => {
      vigente = false
    }
  }, [productoId, recarga])

  const disponibles = catalogo
    .filter((insumo) => !ingredientes.some((item) => item.insumo === insumo.id))
    .map((insumo) => ({ valor: String(insumo.id), etiqueta: insumo.nombre }))

  const unidadSeleccionada = catalogo.find((insumo) => String(insumo.id) === seleccion)?.unidad_medida

  async function agregar() {
    const nuevosErrores = {}
    if (!seleccion) nuevosErrores.insumo = 'Selecciona un ingrediente.'
    if (cantidad === '' || Number.isNaN(Number(cantidad)) || Number(cantidad) <= 0) {
      nuevosErrores.cantidad_necesaria = 'La cantidad debe ser mayor que 0.'
    }
    setErrores(nuevosErrores)
    setError(null)
    if (Object.keys(nuevosErrores).length > 0) return

    setGuardando(true)
    try {
      await agregarIngrediente(productoId, {
        insumo: Number(seleccion),
        cantidad_necesaria: cantidad,
        es_excluible: excluible,
      })
      setSeleccion('')
      setCantidad('1')
      setExcluible(false)
      setRecarga((valor) => valor + 1)
    } catch (err) {
      const { general, campos } = interpretarError(err)
      setError(general)
      setErrores(campos)
    } finally {
      setGuardando(false)
    }
  }

  async function cambiarExcluible(item, valor) {
    setActualizando(item.id)
    setError(null)
    try {
      await actualizarIngrediente(productoId, item.id, { es_excluible: valor })
      setRecarga((actual) => actual + 1)
    } catch (err) {
      setError(interpretarError(err).general)
    } finally {
      setActualizando(null)
    }
  }

  async function quitar(item) {
    if (!window.confirm(`¿Quitar "${item.insumo_nombre}" de este producto?`)) return
    try {
      await quitarIngrediente(productoId, item.id)
      setRecarga((valor) => valor + 1)
    } catch (err) {
      setError(interpretarError(err).general)
    }
  }

  if (cargando) {
    return <p className="text-texto-suave">Cargando ingredientes…</p>
  }

  return (
    <div className="flex flex-col gap-4">
      {error && <Alerta tipo="error" titulo={error} />}

      {ingredientes.length === 0 ? (
        <p className="text-texto-suave">Este producto todavía no tiene ingredientes.</p>
      ) : (
        <ul className="flex flex-col gap-2">
          {ingredientes.map((item) => (
            <li
              key={item.id}
              className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-borde bg-fondo px-3 py-2"
            >
              <div className="flex flex-col gap-2">
                <p className="font-medium">
                  {item.insumo_nombre}{' '}
                  <span className="text-texto-suave">
                    · {formatearCantidad(item.cantidad_necesaria, item.unidad_medida)}
                  </span>
                </p>
                <Casilla
                  etiqueta="El cliente puede quitarlo"
                  checked={item.es_excluible}
                  disabled={actualizando === item.id}
                  onChange={(evento) => cambiarExcluible(item, evento.target.checked)}
                />
                {!item.insumo_activo && (
                  <p className="text-sm text-aviso">Ingrediente eliminado del catálogo.</p>
                )}
              </div>
              <Boton
                variante="peligro"
                onClick={() => quitar(item)}
                aria-label={`Quitar ${item.insumo_nombre} del producto`}
              >
                Quitar
              </Boton>
            </li>
          ))}
        </ul>
      )}

      <div role="group" aria-label="Agregar ingrediente" className="flex flex-col gap-3">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-start">
          <Selector
            etiqueta="Ingrediente"
            opciones={disponibles}
            value={seleccion}
            onChange={(evento) => setSeleccion(evento.target.value)}
            error={errores.insumo}
            textoVacio={disponibles.length ? 'Selecciona un ingrediente' : 'No hay más ingredientes activos'}
            className="sm:flex-1"
          />
          <CampoTexto
            etiqueta={unidadSeleccionada ? `Cantidad (${abreviaturaUnidad(unidadSeleccionada)})` : 'Cantidad'}
            type="number"
            inputMode="decimal"
            min="0"
            step="any"
            value={cantidad}
            onChange={(evento) => setCantidad(evento.target.value)}
            error={errores.cantidad_necesaria}
            className="sm:w-44"
          />
        </div>
        <Casilla
          etiqueta="El cliente puede quitarlo"
          descripcion="Si no la marcas, el cliente no podrá pedir el plato sin este ingrediente."
          checked={excluible}
          onChange={(evento) => setExcluible(evento.target.checked)}
        />
        <Boton onClick={agregar} cargando={guardando} className="self-start">
          Agregar ingrediente
        </Boton>
      </div>
    </div>
  )
}
