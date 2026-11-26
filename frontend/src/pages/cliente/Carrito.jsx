import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { calcularResumenCarrito, validarLineaCarrito } from '../../api/menu.js'
import { interpretarError } from '../../api/errores.js'
import { useCarrito } from '../../carrito/useCarrito.js'
import { useLimpiarCarrito } from '../../carrito/useLimpiarCarrito.js'
import Contador from '../../components/carrito/Contador.jsx'
import PersonalizarProducto from '../../components/carrito/PersonalizarProducto.jsx'
import SedeDelCarrito from '../../components/carrito/SedeDelCarrito.jsx'
import Alerta from '../../components/ui/Alerta.jsx'
import Boton from '../../components/ui/Boton.jsx'
import {
  comboParaValidar,
  domicilioDeZona,
  lineaParaValidar,
  subtotalLinea,
  totalCarritoConDescuento,
} from '../../utils/carrito.js'
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

// HU-21, HU-22 & HU-65 · Carrito del cliente con cupones/promociones y desglose dinámico.
export default function Carrito() {
  const {
    sedeId,
    cargando,
    lineas,
    promocion,
    subtotal,
    descuento,
    cambiarCantidad,
    eliminar,
    aplicarPromocion,
    quitarPromocion,
  } = useCarrito()

  const avisoLimpieza = useLimpiarCarrito()
  const [editando, setEditando] = useState(null)
  const [actualizando, setActualizando] = useState(null)
  const [aviso, setAviso] = useState(null)

  // HU-65 · Estado del input de cupón
  const [codigoInput, setCodigoInput] = useState('')
  const [validandoCupon, setValidandoCupon] = useState(false)
  const [errorCupon, setErrorCupon] = useState(null)
  const [mensajeCupon, setMensajeCupon] = useState(null)

  const { pedidoMinimo, tarifaDomicilio } = useZonaEntrega(sedeId)
  const faltante = faltanteMinimo(subtotal, pedidoMinimo)
  const costoDomicilio = domicilioDeZona(subtotal, tarifaDomicilio)
  const total = totalCarritoConDescuento(subtotal, descuento, costoDomicilio ?? 0)

  // Si cambia el subtotal (por editar cantidades o eliminar líneas) con un cupón activo,
  // revalidamos contra el backend para asegurar que sigue cumpliendo condiciones.
  useEffect(() => {
    if (!promocion || !sedeId || lineas.length === 0) return undefined
    let vigente = true
    const lineasProductos = lineas.filter((l) => !l.combo).map(lineaParaValidar)
    const lineasCombos = lineas.filter((l) => Boolean(l.combo)).map(comboParaValidar)
    calcularResumenCarrito(sedeId, {
      lineas: lineasProductos,
      combos: lineasCombos,
      codigoPromocion: promocion.codigo,
    })
      .then((res) => {
        if (vigente && res.promocion) {
          aplicarPromocion(res.promocion)
        }
      })
      .catch((err) => {
        if (!vigente) return
        const { general, campos } = interpretarError(err)
        const motivo =
          campos.codigo_promocion ?? Object.values(campos)[0] ?? general ?? 'El cupón ya no aplica.'
        quitarPromocion()
        setMensajeCupon(null)
        setErrorCupon(motivo)
      })
    return () => {
      vigente = false
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [subtotal, sedeId])

  async function nuevaCantidad(linea, cantidad) {
    setAviso(null)
    if (linea.combo || cantidad < linea.cantidad) {
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

  // HU-65 · Aplicar cupón/promoción (máximo 1 por pedido; reemplaza si había otro)
  async function handleAplicarCupon(e) {
    e.preventDefault()
    const codigo = codigoInput.trim()
    if (!codigo) return

    setErrorCupon(null)
    setMensajeCupon(null)
    setValidandoCupon(true)
    try {
      const lineasProductos = lineas.filter((l) => !l.combo).map(lineaParaValidar)
      const lineasCombos = lineas.filter((l) => Boolean(l.combo)).map(comboParaValidar)

      const res = await calcularResumenCarrito(sedeId, {
        lineas: lineasProductos,
        combos: lineasCombos,
        codigoPromocion: codigo,
      })
      if (res.promocion) {
        aplicarPromocion(res.promocion)
        setCodigoInput('')
        setMensajeCupon(
          `Cupón "${res.promocion.nombre}" aplicado (−${formatearPrecio(res.descuento)}).`,
        )
      }
    } catch (err) {
      const { general, campos } = interpretarError(err)
      const motivo =
        campos.codigo_promocion ??
        Object.values(campos)[0] ??
        general ??
        'No se pudo aplicar el cupón.'
      setErrorCupon(motivo)
    } finally {
      setValidandoCupon(false)
    }
  }

  // HU-65 · Criterio 4: Remover cupón y restaurar el total original
  function handleQuitarCupon() {
    quitarPromocion()
    setErrorCupon(null)
    setMensajeCupon(null)
  }

  // HU-21: el carrito viene del servidor; mientras llega no se dice que está vacío
  if (lineas.length === 0 && cargando) {
    return (
      <div className="flex flex-col items-start gap-4">
        <h1 className="text-2xl font-bold">Tu carrito</h1>
        <p className="text-texto-suave" role="status">
          Cargando tu carrito…
        </p>
      </div>
    )
  }

  if (lineas.length === 0) {
    return (
      <div className="flex flex-col items-start gap-4">
        <h1 className="text-2xl font-bold">Tu carrito</h1>
        {avisoLimpieza && <Alerta tipo="aviso" titulo={avisoLimpieza} />}
        <p className="text-texto-suave">Todavía no has agregado productos.</p>
        <Link
          to="/menu"
          className="inline-flex min-h-11 items-center rounded-lg bg-marca px-4 font-medium text-sobre-marca hover:bg-marca-oscura"
        >
          Ver el menú
        </Link>
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-6">
      <header className="flex flex-col gap-1">
        <h1 className="text-2xl font-bold">Tu carrito</h1>
        <SedeDelCarrito sedeId={sedeId} />
      </header>

      {avisoLimpieza && <Alerta tipo="aviso" titulo={avisoLimpieza} />}
      {aviso && <Alerta tipo={aviso.tipo} titulo={aviso.texto} />}

      <ul className="flex flex-col gap-3">
        {lineas.map((linea) => {
          const esCombo = Boolean(linea.combo)
          const nombreItem = esCombo ? linea.combo.nombre : linea.producto.nombre

          return (
            <li
              key={linea.id}
              className="flex flex-col gap-3 rounded-xl border border-borde bg-superficie p-4 sm:flex-row sm:items-center"
            >
              {linea.producto?.imagen ? (
                <img
                  src={linea.producto.imagen}
                  alt=""
                  className="aspect-video w-full rounded-lg object-cover sm:w-28"
                />
              ) : (
                <div aria-hidden="true" className="hidden h-16 w-28 rounded-lg bg-superficie-alta sm:block" />
              )}

              <div className="flex-1">
                <h2 className="font-bold">{nombreItem}</h2>
                {esCombo && linea.combo.productos_incluidos?.length > 0 && (
                  <p className="text-sm text-texto-suave">
                    Incluye:{' '}
                    {linea.combo.productos_incluidos
                      .map((item) => `${item.cantidad}× ${item.nombre}`)
                      .join(' · ')}
                  </p>
                )}
                {!esCombo && describirVariantes(linea) && (
                  <p className="text-sm text-texto-suave">{describirVariantes(linea)}</p>
                )}
                <p className="text-sm text-texto-suave">{formatearPrecio(linea.precio_unitario)} c/u</p>
              </div>

              <div className="flex flex-wrap items-center justify-between gap-3 sm:justify-end">
                <Contador
                  etiqueta={`Cantidad de ${nombreItem}`}
                  valor={linea.cantidad}
                  minimo={1}
                  disabled={actualizando === linea.id}
                  alCambiar={(cantidad) => nuevaCantidad(linea, cantidad)}
                />
                <p className="w-28 text-right text-lg font-semibold">{formatearPrecio(subtotalLinea(linea))}</p>
                <div className="flex gap-2">
                  {!esCombo && (
                    <Boton variante="secundario" onClick={() => setEditando(linea)}>
                      Editar
                    </Boton>
                  )}
                  <Boton
                    variante="peligro"
                    onClick={() => eliminar(linea.id)}
                    aria-label={`Eliminar ${nombreItem} del carrito`}
                  >
                    Eliminar
                  </Boton>
                </div>
              </div>
            </li>
          )
        })}
      </ul>

      {/* HU-65: Sección de Cupón / Promoción (máximo 1 promoción por pedido) */}
      <div className="flex flex-col gap-3 rounded-xl border border-borde bg-superficie p-4">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h2 className="text-base font-bold">Cupón o promoción</h2>
          <span className="text-xs text-texto-suave">Máximo 1 promoción por pedido</span>
        </div>

        {promocion ? (
          <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-exito bg-exito/10 px-3 py-2.5">
            <div>
              <p className="text-sm font-bold text-exito">
                ✓ {promocion.nombre}{' '}
                <span className="font-normal">
                  (
                  {promocion.tipo_descuento === 'porcentaje'
                    ? `${Number(promocion.valor)}% de descuento`
                    : `${formatearPrecio(promocion.valor)} de descuento`}
                  )
                </span>
              </p>
              {promocion.descripcion && (
                <p className="text-xs text-texto-suave">{promocion.descripcion}</p>
              )}
            </div>
            <Boton
              type="button"
              variante="secundario"
              onClick={handleQuitarCupon}
              aria-label="Quitar cupón aplicado"
            >
              Quitar
            </Boton>
          </div>
        ) : (
          <form onSubmit={handleAplicarCupon} className="flex flex-col gap-2 sm:flex-row">
            <input
              type="text"
              value={codigoInput}
              onChange={(e) => {
                setCodigoInput(e.target.value)
                if (errorCupon) setErrorCupon(null)
              }}
              placeholder="Ingresa el código de descuento"
              aria-label="Código de descuento"
              disabled={validandoCupon}
              className="min-h-11 flex-1 rounded-lg border border-borde bg-fondo px-3 text-texto placeholder:text-texto-suave focus:border-marca focus:outline-none"
            />
            <Boton
              type="submit"
              variante="secundario"
              cargando={validandoCupon}
              disabled={!codigoInput.trim() || validandoCupon}
            >
              Aplicar
            </Boton>
          </form>
        )}

        {errorCupon && <Alerta tipo="error" titulo={errorCupon} />}
        {mensajeCupon && !errorCupon && <Alerta tipo="exito" titulo={mensajeCupon} />}
      </div>

      {/* HU-22 & HU-65: Desglose completo de Totales (Subtotal, Descuento, Domicilio y Total) */}
      <div className="flex flex-col items-end gap-3 border-t border-borde pt-4">
        <div className="flex w-full flex-col gap-1.5 sm:w-80">
          <div className="flex justify-between text-sm text-texto-suave">
            <span>Subtotal</span>
            <span>{formatearPrecio(subtotal)}</span>
          </div>
          {descuento > 0 && (
            <div className="flex justify-between text-sm font-medium text-exito">
              <span>Descuento ({promocion?.nombre})</span>
              <span>−{formatearPrecio(descuento)}</span>
            </div>
          )}
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
            className="mt-2 inline-flex min-h-11 w-full items-center justify-center rounded-lg bg-marca px-6 font-bold text-sobre-marca hover:bg-marca-oscura sm:w-auto"
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