import { useState } from 'react'
import { Link } from 'react-router-dom'
import { validarLineaCarrito } from '../../api/menu.js'
import { interpretarError } from '../../api/errores.js'
import { useCarrito } from '../../carrito/useCarrito.js'
import Contador from '../../components/carrito/Contador.jsx'
import PersonalizarProducto from '../../components/carrito/PersonalizarProducto.jsx'
import Alerta from '../../components/ui/Alerta.jsx'
import Boton from '../../components/ui/Boton.jsx'
import { domicilioDeZona, lineaParaValidar, subtotalLinea, totalCarrito } from '../../utils/carrito.js'
import { formatearPrecio } from '../../utils/formato.js'
import { useZonaEntrega } from '../../carrito/useZonaEntrega.js'
import { faltanteMinimo } from '../../utils/pedidoMinimo.js'

function describirVariantes(linea) {
  const partes = []
  if (linea.tamano) partes.push(linea.tamano.nombre)
  for (const item of linea.adiciones) {
    partes.push(item.cantidad > 1 ? `${item.nombre} ×${item.cantidad}` : item.nombre)
  }
  for (const item of linea.exclusiones) partes.push(`Sin ${item.nombre.toLowerCase()}`)
  return partes.join(' · ')
}

// HU-21 & HU-22 · Carrito del cliente: líneas personalizadas, subtotal, domicilio y total.
export default function Carrito() {
  const { sedeId, lineas, subtotal, cambiarCantidad, eliminar } = useCarrito()
  const [editando, setEditando] = useState(null)
  const [actualizando, setActualizando] = useState(null)
  const [aviso, setAviso] = useState(null)
  // HU-22: el domicilio sale de la zona de la dirección del cliente (no de una tarifa fija).
  const { pedidoMinimo, tarifaDomicilio } = useZonaEntrega()
  const faltante = faltanteMinimo(subtotal, pedidoMinimo)
  const costoDomicilio = domicilioDeZona(subtotal, tarifaDomicilio)
  const total = totalCarrito(subtotal, costoDomicilio ?? 0)

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

      {/* HU-22: Desglose completo de Totales (Subtotal, Costo de domicilio y Total) */}
      <div className="flex flex-col items-end gap-3 border-t border-borde pt-4">
        <div className="flex w-full flex-col gap-1.5 sm:w-72">
          <div className="flex justify-between text-sm text-texto-suave">
            <span>Subtotal</span>
            <span>{formatearPrecio(subtotal)}</span>
          </div>
          <div className="flex justify-between text-sm text-texto-suave">
            <span>Costo de domicilio</span>
            <span>
              {costoDomicilio === null ? 'Se calcula con tu dirección' : formatearPrecio(costoDomicilio)}
            </span>
          </div>
          <div className="flex justify-between border-t border-borde pt-2 text-xl font-bold text-texto">
            <span>Total</span>
            <span aria-live="polite">{formatearPrecio(total)}</span>
          </div>
        </div>

        {/* Botón para proceder al flujo de la HU-23 */}
        {faltante > 0 && (
          <Alerta
            tipo="aviso"
            titulo={`Te faltan ${formatearPrecio(faltante)} para llegar al pedido mínimo de tu zona (${formatearPrecio(pedidoMinimo)}).`}
            className="w-full sm:w-auto"
          >
            El mínimo se calcula sobre los productos, sin el domicilio.
          </Alerta>
        )}

        {faltante > 0 ? (
          <Boton disabled className="mt-2 w-full sm:w-auto">
            Proceder a la compra
          </Boton>
        ) : (
          <Link
            to="/checkout"
            className="mt-2 inline-flex min-h-11 w-full items-center justify-center rounded-lg bg-marca px-6 font-bold text-white hover:bg-marca-oscura sm:w-auto"
          >
            Proceder a la compra
          </Link>
        )}
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