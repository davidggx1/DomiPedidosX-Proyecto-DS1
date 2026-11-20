import { useState, useEffect } from 'react'
import { crearPedidoOperador } from '../../api/pedidos.js'
import { listarProductos, listarTamanosProducto } from '../../api/menu.js' // API de catálogo
import Boton from '../../components/ui/Boton.jsx'
import Alerta from '../../components/ui/Alerta.jsx'
import Casilla from '../../components/ui/Casilla.jsx'
import Modal from '../../components/ui/Modal.jsx'
import { useMensajeTemporal } from '../../components/ui/useMensajeTemporal.js'
import { formatearPrecio } from '../../utils/formato.js'
import {
  MAXIMO_POR_LINEA,
  agregarLinea,
  cambiarCantidad,
  itemsParaEnviar,
  lineaLlena,
  mensajeErrorPedido,
  normalizarCantidad,
  precioConTamano,
  quitarLinea,
} from '../../utils/pedidoOperador.js'
import { useEstadoCapacidad } from '../../capacidad/useEstadoCapacidad.js'
import { errorDeCapacidad, interpretarCapacidad } from '../../utils/capacidad.js'

// Digits the quantity field accepts: enough for MAXIMO_POR_LINEA (50)
const DIGITOS_CANTIDAD = String(MAXIMO_POR_LINEA).length

// − [n] + for one cart line. The typed text is kept while editing and applied on
// blur or Enter, so the operator can clear the field and type "25".
function CantidadLinea({ item, alCambiar }) {
  const [texto, setTexto] = useState(String(item.cantidad))
  const [anterior, setAnterior] = useState(item.cantidad)
  if (anterior !== item.cantidad) {
    setAnterior(item.cantidad)
    setTexto(String(item.cantidad))
  }

  // Always show the value that really applies (e.g. 50 after typing 80, even if it was already 50)
  function aplicar() {
    const cantidad = normalizarCantidad(texto) ?? item.cantidad
    setTexto(String(cantidad))
    if (cantidad !== item.cantidad) alCambiar(cantidad)
  }

  const boton = 'h-7 w-7 rounded-md border border-borde text-base leading-none hover:border-marca disabled:opacity-40'
  return (
    <span className="flex items-center gap-1">
      <button
        type="button"
        className={boton}
        onClick={() => alCambiar(item.cantidad - 1)}
        disabled={item.cantidad <= 1}
        aria-label={`Una ${item.nombre} menos`}
      >
        −
      </button>
      <input
        type="text"
        inputMode="numeric"
        maxLength={DIGITOS_CANTIDAD}
        value={texto}
        onChange={(e) => setTexto(e.target.value.replace(/\D/g, '').slice(0, DIGITOS_CANTIDAD))}
        onBlur={aplicar}
        onKeyDown={(e) => e.key === 'Enter' && (e.preventDefault(), aplicar())}
        className="h-7 w-12 rounded-md border border-borde bg-fondo text-center tabular-nums"
        aria-label={`Cantidad de ${item.nombre}`}
      />
      <button
        type="button"
        className={boton}
        onClick={() => alCambiar(item.cantidad + 1)}
        disabled={item.cantidad >= MAXIMO_POR_LINEA}
        aria-label={`Una ${item.nombre} más`}
      >
        +
      </button>
    </span>
  )
}

export default function CrearPedidoOperador() {
  const [origen, setOrigen] = useState('mostrador') // 'mostrador' o 'telefonico'
  const [metodoPago, setMetodoPago] = useState('efectivo')
  const [productos, setProductos] = useState([])
  const [busqueda, setBusqueda] = useState('')
  const [carrito, setCarrito] = useState([])
  const [cargando, setCargando] = useState(false)
  const [mensaje, setMensaje] = useMensajeTemporal()
  const [confirmaSinFranja, setConfirmaSinFranja] = useState(false)
  // Producto con tamaños esperando que el operador elija uno: { producto, tamanos }
  const [eligiendoTamano, setEligiendoTamano] = useState(null)

  // HU-61: capacity of the operator's own sede
  const { estado: estadoCapacidad, refrescar: refrescarCapacidad } = useEstadoCapacidad()
  const capacidadInfo = interpretarCapacidad(estadoCapacidad)

  useEffect(() => {
    listarProductos().then(setProductos).catch(console.error)
  }, [])

  const agregarAlCarrito = (prod, tamano = null) => {
    if (lineaLlena(carrito, prod, tamano)) {
      const nombre = tamano ? `${prod.nombre} (${tamano.nombre})` : prod.nombre
      setMensaje({ tipo: 'error', texto: `Máximo ${MAXIMO_POR_LINEA} unidades de ${nombre} por pedido.` })
      return
    }
    setCarrito((prev) => agregarLinea(prev, prod, tamano))
  }

  // Si el producto tiene tamaños activos, el operador debe elegir uno (como en la web).
  const alElegirProducto = async (prod) => {
    try {
      const tamanos = await listarTamanosProducto(prod.id)
      if (tamanos.length > 0) {
        setEligiendoTamano({ producto: prod, tamanos })
        return
      }
    } catch (err) {
      console.error(err)
      setMensaje({ tipo: 'error', texto: 'No se pudieron cargar los tamaños del producto.' })
      return
    }
    agregarAlCarrito(prod)
  }

  const elegirTamano = (tamano) => {
    agregarAlCarrito(eligiendoTamano.producto, tamano)
    setEligiendoTamano(null)
  }

  const subtotal = carrito.reduce((sum, item) => sum + item.precio * item.cantidad, 0)
  const domicilio = origen === 'telefonico' ? 4000 : 0
  const total = subtotal + domicilio

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (carrito.length === 0) return setMensaje({ tipo: 'error', texto: 'Agrega al menos un producto.' })

    try {
      setCargando(true)
      setMensaje(null)

      // Payload completo compatible con CrearPedidoOperadorSerializer
      const payload = {
        origen,
        metodo_pago: metodoPago,
        cliente_id: null,
        direccion_id: null,
        observaciones: '',
        confirmar_sin_franja: capacidadInfo.requiereConfirmacion && confirmaSinFranja,
        items: itemsParaEnviar(carrito),
      }

      const res = await crearPedidoOperador(payload)
      setMensaje({ tipo: 'exito', texto: `¡Pedido #${res.numero_pedido} registrado con éxito!` })
      setCarrito([])
      setConfirmaSinFranja(false)
      refrescarCapacidad()
    } catch (err) {
      console.error('Error backend 400:', err.response?.data)
      const errorCap = errorDeCapacidad(err)
      if (errorCap) {
        setMensaje({ tipo: 'error', texto: errorCap.detail })
        refrescarCapacidad()
      } else {
        setMensaje({ tipo: 'error', texto: mensajeErrorPedido(err.response?.data, carrito) })
      }
    } finally {
      setCargando(false)
    }
  }

  const productosFiltrados = productos.filter((p) =>
    p.nombre.toLowerCase().includes(busqueda.toLowerCase())
  )

  return (
    <div className="grid grid-cols-1 gap-6 p-4 lg:grid-cols-3">
      {/* Catálogo y Buscador */}
      <div className="space-y-4 lg:col-span-2">
        <h1 className="text-2xl font-bold">Crear Pedido (Mostrador / Teléfono)</h1>
        <input
          type="text"
          placeholder="Buscar producto..."
          value={busqueda}
          onChange={(e) => setBusqueda(e.target.value)}
          className="w-full rounded-lg border border-borde p-3"
        />
        <div className="grid grid-cols-2 gap-3 md:grid-cols-3">
          {productosFiltrados.map((prod) => (
            <div
              key={prod.id}
              onClick={() => alElegirProducto(prod)}
              className="cursor-pointer rounded-xl border border-borde p-4 hover:border-marca"
            >
              <h3 className="font-semibold">{prod.nombre}</h3>
              <p className="text-sm text-texto-suave">{formatearPrecio(prod.precio_base)}</p>
            </div>
          ))}
        </div>
      </div>

      {/* Resumen de Venta */}
      <div className="rounded-xl border border-borde bg-superficie p-5 shadow-sm space-y-4">
        <h2 className="text-xl font-bold border-b pb-2">Resumen de Venta</h2>
        {mensaje && <Alerta tipo={mensaje.tipo} titulo={mensaje.texto} />}

        {capacidadInfo.aviso && (
          <Alerta tipo={capacidadInfo.aviso.tipo} titulo={capacidadInfo.aviso.texto} />
        )}
        {capacidadInfo.requiereConfirmacion && (
          <Casilla
            etiqueta="Crear el pedido sin franja de capacidad"
            checked={confirmaSinFranja}
            onChange={(e) => setConfirmaSinFranja(e.target.checked)}
          />
        )}

        <div>
          <label className="block text-sm font-semibold mb-1">Origen:</label>
          <select
            value={origen}
            onChange={(e) => setOrigen(e.target.value)}
            className="w-full rounded-md border p-2"
          >
            <option value="mostrador">Mostrador (Para Llevar)</option>
            <option value="telefonico">Telefónico (Domicilio)</option>
          </select>
        </div>

        <div>
          <label className="block text-sm font-semibold mb-1">Método de Pago:</label>
          <select
            value={metodoPago}
            onChange={(e) => setMetodoPago(e.target.value)}
            className="w-full rounded-md border p-2"
          >
            <option value="efectivo">Efectivo</option>
            <option value="tarjeta">Tarjeta</option>
            <option value="transferencia">Transferencia</option>
          </select>
        </div>

        <div className="space-y-2 border-t pt-3">
          {carrito.map((item) => (
            <div key={item.clave} className="flex flex-wrap items-center justify-between gap-2 text-sm">
              <span className="min-w-0 flex-1">{item.nombre}</span>
              <CantidadLinea
                item={item}
                alCambiar={(cantidad) => setCarrito((prev) => cambiarCantidad(prev, item.clave, cantidad))}
              />
              <span className="flex items-center gap-2">
                {formatearPrecio(item.precio * item.cantidad)}
                <button
                  type="button"
                  onClick={() => setCarrito((prev) => quitarLinea(prev, item.clave))}
                  className="text-texto-suave hover:text-error"
                  aria-label={`Quitar ${item.nombre}`}
                >
                  ✕
                </button>
              </span>
            </div>
          ))}
        </div>

        <div className="border-t pt-3 space-y-1 font-bold">
          <div className="flex justify-between text-sm">
            <span>Subtotal:</span>
            <span>{formatearPrecio(subtotal)}</span>
          </div>
          {origen === 'telefonico' && (
            <div className="flex justify-between text-sm text-texto-suave">
              <span>Domicilio:</span>
              <span>{formatearPrecio(domicilio)}</span>
            </div>
          )}
          <div className="flex justify-between text-lg text-marca pt-2">
            <span>Total:</span>
            <span>{formatearPrecio(total)}</span>
          </div>
        </div>

        <Boton
          variante="primario"
          className="w-full mt-4"
          disabled={
            cargando ||
            carrito.length === 0 ||
            capacidadInfo.bloqueado ||
            (capacidadInfo.requiereConfirmacion && !confirmaSinFranja)
          }
          onClick={handleSubmit}
        >
          {cargando ? 'Procesando...' : 'Confirmar Pedido'}
        </Boton>
      </div>

      {eligiendoTamano && (
        <Modal
          titulo={`Tamaño de ${eligiendoTamano.producto.nombre}`}
          alCerrar={() => setEligiendoTamano(null)}
          acciones={
            <Boton variante="secundario" onClick={() => setEligiendoTamano(null)}>
              Cancelar
            </Boton>
          }
        >
          <div className="grid gap-2">
            {eligiendoTamano.tamanos.map((tamano) => (
              <button
                key={tamano.id}
                type="button"
                onClick={() => elegirTamano(tamano)}
                className="flex justify-between rounded-xl border border-borde p-3 text-left hover:border-marca"
              >
                <span className="font-semibold">{tamano.nombre}</span>
                <span>{formatearPrecio(precioConTamano(eligiendoTamano.producto, tamano))}</span>
              </button>
            ))}
          </div>
        </Modal>
      )}
    </div>
  )
}