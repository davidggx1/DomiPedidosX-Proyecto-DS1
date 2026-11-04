import { useState } from 'react'
import { Link } from 'react-router-dom'
import { validarLineaCarrito } from '../../api/menu.js'
import { interpretarError } from '../../api/errores.js'
import { useCarrito } from '../../carrito/useCarrito.js'
import Contador from '../../components/carrito/Contador.jsx'
import PersonalizarProducto from '../../components/carrito/PersonalizarProducto.jsx'
import Alerta from '../../components/ui/Alerta.jsx'
import Boton from '../../components/ui/Boton.jsx'
import { lineaParaValidar, subtotalLinea } from '../../utils/carrito.js'
import { formatearPrecio } from '../../utils/formato.js'

function describirVariantes(linea) {
  const partes = []
  if (linea.tamano) partes.push(linea.tamano.nombre)
  for (const item of linea.adiciones) {
    partes.push(item.cantidad > 1 ? `${item.nombre} ×${item.cantidad}` : item.nombre)
  }
  for (const item of linea.exclusiones) partes.push(`Sin ${item.nombre.toLowerCase()}`)
  return partes.join(' · ')
}

// HU-21 · Carrito del cliente: líneas personalizadas y subtotal.
// La confirmación del pedido llega con HU-23.
export default function Carrito() {
  const { sedeId, lineas, subtotal, cambiarCantidad, eliminar } = useCarrito()
  const [editando, setEditando] = useState(null)
  const [actualizando, setActualizando] = useState(null)
  const [aviso, setAviso] = useState(null)

  // Al subir la cantidad se revalida con el backend (stock de la sede).
  async function nuevaCantidad(linea, cantidad) {
    setAviso(null)
    if (cantidad < linea.cantidad) {
      cambiarCantidad(linea.id, cantidad)
      return
    }
    setActualizando(linea.id)
    try {
      await validarLineaCarrito(sedeId, { ...lineaParaValidar(linea), cantidad })
      cambiarCantidad(linea.id, cantidad)
    } catch (err) {
      const { general, campos } = interpretarError(err)
      setAviso({ tipo: 'error', texto: Object.values(campos)[0] ?? general })
    } finally {
      setActualizando(null)
    }
  }

  if (lineas.length === 0) {
    return (
      <div className="flex flex-col items-start gap-4">
        <h1 className="text-2xl font-bold">Tu carrito</h1>
        <p className="text-texto-suave">Todavía no has agregado productos.</p>
        <Link
          to="/menu"
          className="inline-flex min-h-11 items-center rounded-lg bg-marca px-4 font-medium text-white hover:bg-marca-oscura"
        >
          Ver el menú
        </Link>
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-6">
      <h1 className="text-2xl font-bold">Tu carrito</h1>

      {aviso && <Alerta tipo={aviso.tipo} titulo={aviso.texto} />}

      <ul className="flex flex-col gap-3">
        {lineas.map((linea) => (
          <li
            key={linea.id}
            className="flex flex-col gap-3 rounded-xl border border-borde bg-superficie p-4 sm:flex-row sm:items-center"
          >
            {linea.producto.imagen ? (
              <img
                src={linea.producto.imagen}
                alt=""
                className="aspect-video w-full rounded-lg object-cover sm:w-28"
              />
            ) : (
              <div aria-hidden="true" className="hidden h-16 w-28 rounded-lg bg-superficie-alta sm:block" />
            )}

            <div className="flex-1">
              <h2 className="font-bold">{linea.producto.nombre}</h2>
              {describirVariantes(linea) && (
                <p className="text-sm text-texto-suave">{describirVariantes(linea)}</p>
              )}
              <p className="text-sm text-texto-suave">{formatearPrecio(linea.precio_unitario)} c/u</p>
            </div>

            <div className="flex flex-wrap items-center justify-between gap-3 sm:justify-end">
              <Contador
                etiqueta={`Cantidad de ${linea.producto.nombre}`}
                valor={linea.cantidad}
                minimo={1}
                disabled={actualizando === linea.id}
                alCambiar={(cantidad) => nuevaCantidad(linea, cantidad)}
              />
              <p className="w-28 text-right text-lg font-semibold">{formatearPrecio(subtotalLinea(linea))}</p>
              <div className="flex gap-2">
                <Boton variante="secundario" onClick={() => setEditando(linea)}>
                  Editar
                </Boton>
                <Boton
                  variante="peligro"
                  onClick={() => eliminar(linea.id)}
                  aria-label={`Eliminar ${linea.producto.nombre} del carrito`}
                >
                  Eliminar
                </Boton>
              </div>
            </div>
          </li>
        ))}
      </ul>

      <div className="flex flex-col items-end gap-1 border-t border-borde pt-4">
        <p className="text-texto-suave">Subtotal</p>
        <p className="text-2xl font-bold" aria-live="polite">
          {formatearPrecio(subtotal)}
        </p>
        <p className="text-sm text-texto-suave">El domicilio y los descuentos se calculan al confirmar el pedido.</p>
      </div>

      {editando && (
        <PersonalizarProducto
          sedeId={sedeId}
          producto={editando.producto}
          linea={editando}
          alCerrar={() => setEditando(null)}
          alAgregar={(_, fusionada) =>
            setAviso({
              tipo: 'exito',
              texto: fusionada ? 'La línea quedó igual a otra y se unieron.' : 'Línea actualizada.',
            })
          }
        />
      )}
    </div>
  )
}
