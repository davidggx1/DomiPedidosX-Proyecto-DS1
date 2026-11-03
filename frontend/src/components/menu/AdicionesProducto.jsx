import { useEffect, useState } from 'react'
import {
  asignarAdicion,
  listarAdiciones,
  listarAdicionesProducto,
  quitarAdicionProducto,
} from '../../api/menu.js'
import { interpretarError } from '../../api/errores.js'
import { formatearPrecio } from '../../utils/formato.js'
import Alerta from '../ui/Alerta.jsx'
import Boton from '../ui/Boton.jsx'
import CampoTexto from '../ui/CampoTexto.jsx'
import Selector from '../ui/Selector.jsx'

// Sección "Adiciones" de un producto (HU-76): asigna o quita adiciones del catálogo.
// Pensada para reutilizarse dentro del formulario de producto (HU-11), por eso no
// usa <form>: un formulario no puede ir dentro de otro.
export default function AdicionesProducto({ productoId }) {
  const [asignadas, setAsignadas] = useState([])
  const [catalogo, setCatalogo] = useState([])
  const [cargando, setCargando] = useState(true)
  const [error, setError] = useState(null)
  const [seleccion, setSeleccion] = useState('')
  const [maxCantidad, setMaxCantidad] = useState('1')
  const [errores, setErrores] = useState({})
  const [guardando, setGuardando] = useState(false)
  const [recarga, setRecarga] = useState(0)

  useEffect(() => {
    let vigente = true
    Promise.all([listarAdicionesProducto(productoId), listarAdiciones({ activa: true })])
      .then(([delProducto, activas]) => {
        if (!vigente) return
        setAsignadas(delProducto)
        setCatalogo(activas)
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
    .filter((adicion) => !asignadas.some((item) => item.adicion === adicion.id))
    .map((adicion) => ({
      valor: String(adicion.id),
      etiqueta: `${adicion.nombre} (+${formatearPrecio(adicion.precio)})`,
    }))

  async function asignar() {
    const nuevosErrores = {}
    if (!seleccion) nuevosErrores.adicion = 'Selecciona una adición.'
    if (!Number.isInteger(Number(maxCantidad)) || Number(maxCantidad) < 1) {
      nuevosErrores.max_cantidad = 'La cantidad máxima debe ser un número entero de al menos 1.'
    }
    setErrores(nuevosErrores)
    setError(null)
    if (Object.keys(nuevosErrores).length > 0) return

    setGuardando(true)
    try {
      await asignarAdicion(productoId, {
        adicion: Number(seleccion),
        max_cantidad: Number(maxCantidad),
      })
      setSeleccion('')
      setMaxCantidad('1')
      setRecarga((valor) => valor + 1)
    } catch (err) {
      const { general, campos } = interpretarError(err)
      setError(general)
      setErrores(campos)
    } finally {
      setGuardando(false)
    }
  }

  async function quitar(item) {
    if (!window.confirm(`¿Quitar "${item.adicion_nombre}" de este producto?`)) return
    try {
      await quitarAdicionProducto(productoId, item.id)
      setRecarga((valor) => valor + 1)
    } catch (err) {
      setError(interpretarError(err).general)
    }
  }

  if (cargando) {
    return <p className="text-texto-suave">Cargando adiciones…</p>
  }

  return (
    <div className="flex flex-col gap-4">
      {error && <Alerta tipo="error" titulo={error} />}

      {asignadas.length === 0 ? (
        <p className="text-texto-suave">Este producto todavía no tiene adiciones.</p>
      ) : (
        <ul className="flex flex-col gap-2">
          {asignadas.map((item) => (
            <li
              key={item.id}
              className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-borde bg-fondo px-3 py-2"
            >
              <div>
                <p className="font-medium">
                  {item.adicion_nombre}{' '}
                  <span className="text-texto-suave">
                    +{formatearPrecio(item.adicion_precio)} · máx. {item.max_cantidad}
                  </span>
                </p>
                {!item.adicion_activa && (
                  <p className="text-sm text-aviso">
                    Adición eliminada: los clientes ya no la ven.
                  </p>
                )}
              </div>
              <Boton
                variante="peligro"
                onClick={() => quitar(item)}
                aria-label={`Quitar ${item.adicion_nombre} del producto`}
              >
                Quitar
              </Boton>
            </li>
          ))}
        </ul>
      )}

      <div role="group" aria-label="Asignar adición" className="flex flex-col gap-3 sm:flex-row sm:items-start">
        <Selector
          etiqueta="Adición"
          opciones={disponibles}
          value={seleccion}
          onChange={(evento) => setSeleccion(evento.target.value)}
          error={errores.adicion}
          textoVacio={disponibles.length ? 'Selecciona una adición' : 'No hay más adiciones activas'}
          className="sm:flex-1"
        />
        <CampoTexto
          etiqueta="Cantidad máxima"
          type="number"
          inputMode="numeric"
          min="1"
          step="1"
          value={maxCantidad}
          onChange={(evento) => setMaxCantidad(evento.target.value)}
          error={errores.max_cantidad}
          className="sm:w-40"
        />
        <Boton onClick={asignar} cargando={guardando} className="sm:mt-6">
          Asignar
        </Boton>
      </div>
    </div>
  )
}
