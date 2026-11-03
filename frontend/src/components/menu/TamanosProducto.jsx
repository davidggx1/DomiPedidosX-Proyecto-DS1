import { useCallback, useEffect, useState } from 'react'
import {
  actualizarTamanoProducto,
  crearTamanoProducto,
  eliminarTamanoProducto,
  listarTamanosProducto,
} from '../../api/menu.js'
import { interpretarError } from '../../api/errores.js'
import { formatearPrecio } from '../../utils/formato.js'
import Alerta from '../ui/Alerta.jsx'
import Boton from '../ui/Boton.jsx'

const VACIO = { nombre: '', precio_adicional: '0' }

export default function TamanosProducto({ productoId }) {
  const [tamanos, setTamanos] = useState([])
  const [valores, setValores] = useState(VACIO)
  const [editando, setEditando] = useState(null)
  const [error, setError] = useState(null)
  const [cargando, setCargando] = useState(true)
  const [guardando, setGuardando] = useState(false)

  const cargar = useCallback(async () => {
    try {
      setTamanos(await listarTamanosProducto(productoId))
      setError(null)
    } catch (e) {
      setError(interpretarError(e).general)
    } finally {
      setCargando(false)
    }
  }, [productoId])

  useEffect(() => {
    let vigente = true

    listarTamanosProducto(productoId)
      .then((datos) => {
        if (vigente) {
          setTamanos(datos)
          setError(null)
        }
      })
      .catch((e) => {
        if (vigente) setError(interpretarError(e).general)
      })
      .finally(() => {
        if (vigente) setCargando(false)
      })

    return () => {
      vigente = false
    }
  }, [productoId])

  function limpiar() {
    setValores(VACIO)
    setEditando(null)
  }

  async function guardar(e) {
    e.preventDefault()
    const nombre = valores.nombre.trim()
    const precio = Number(valores.precio_adicional)
    if (!nombre) return setError('El nombre del tamaño es obligatorio.')
    if (valores.precio_adicional === '' || !Number.isFinite(precio) || precio < 0) {
      return setError('El precio adicional debe ser un número mayor o igual a 0.')
    }
    setGuardando(true)
    setError(null)
    try {
      const datos = { nombre, precio_adicional: valores.precio_adicional }
      if (editando) await actualizarTamanoProducto(productoId, editando.id, datos)
      else await crearTamanoProducto(productoId, datos)
      limpiar()
      await cargar()
    } catch (e) {
      const { general, campos } = interpretarError(e)
      setError(campos.nombre || campos.precio_adicional || general)
    } finally {
      setGuardando(false)
    }
  }

  async function eliminar(tamano) {
    if (!window.confirm(`¿Eliminar el tamaño "${tamano.nombre}"? Dejará de ofrecerse, pero se conservará para el historial.`)) return
    try {
      await eliminarTamanoProducto(productoId, tamano.id)
      await cargar()
    } catch (e) {
      setError(interpretarError(e).general)
    }
  }

  return (
    <section className="mt-5 flex flex-col gap-3 border-t border-borde pt-4">
      <div>
        <h3 className="font-semibold">Tamaños del producto</h3>
        <p className="text-sm text-texto-suave">
          El precio indicado es adicional al precio base del producto.
        </p>
      </div>
      {error && <Alerta tipo="error" titulo={error} />}
      <form onSubmit={guardar} className="grid gap-3 sm:grid-cols-[1fr_1fr_auto] sm:items-end">
        <label className="flex flex-col gap-1 text-sm">
          Nombre
          <input
            required maxLength={30} value={valores.nombre}
            onChange={(e) => setValores((v) => ({ ...v, nombre: e.target.value }))}
            placeholder="Ej.: Grande"
            className="rounded-lg border border-borde bg-fondo px-3 py-2"
          />
        </label>
        <label className="flex flex-col gap-1 text-sm">
          Precio adicional (COP)
          <input
            required type="number" min="0" step="0.01" value={valores.precio_adicional}
            onChange={(e) => setValores((v) => ({ ...v, precio_adicional: e.target.value }))}
            className="rounded-lg border border-borde bg-fondo px-3 py-2"
          />
        </label>
        <div className="flex gap-2">
          <Boton tipo="submit" cargando={guardando}>{editando ? 'Guardar' : 'Agregar'}</Boton>
          {editando && <Boton variante="secundario" onClick={limpiar}>Cancelar</Boton>}
        </div>
      </form>
      {cargando ? <p className="text-sm text-texto-suave">Cargando tamaños…</p> : tamanos.length === 0 ? (
        <p className="text-sm text-texto-suave">Este producto todavía no tiene tamaños.</p>
      ) : (
        <ul className="flex flex-col gap-2">
          {tamanos.map((tamano) => (
            <li key={tamano.id} className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-borde p-3">
              <span className="text-sm">
                <strong>{tamano.nombre}</strong>
                <span className="text-texto-suave"> · +{formatearPrecio(tamano.precio_adicional)}</span>
              </span>
              <span className="flex gap-2">
                <Boton variante="secundario" onClick={() => {
                  setEditando(tamano)
                  setValores({ nombre: tamano.nombre, precio_adicional: String(tamano.precio_adicional) })
                }}>Editar</Boton>
                <Boton variante="secundario" onClick={() => eliminar(tamano)}>Eliminar</Boton>
              </span>
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}
