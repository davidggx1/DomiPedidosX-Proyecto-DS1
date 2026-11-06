import { useState, useEffect } from 'react'
import { crearPedidoOperador } from '../../api/pedidos.js'
import { listarProductos } from '../../api/menu.js' // API de catálogo
import Boton from '../../components/ui/Boton.jsx'
import Alerta from '../../components/ui/Alerta.jsx'
import { formatearPrecio } from '../../utils/formato.js'

export default function CrearPedidoOperador() {
  const [origen, setOrigen] = useState('mostrador') // 'mostrador' o 'telefonico'
  const [metodoPago, setMetodoPago] = useState('efectivo')
  const [productos, setProductos] = useState([])
  const [busqueda, setBusqueda] = useState('')
  const [carrito, setCarrito] = useState([])
  const [cargando, setCargando] = useState(false)
  const [mensaje, setMensaje] = useState(null)

  useEffect(() => {
    listarProductos().then(setProductos).catch(console.error)
  }, [])

  const agregarAlCarrito = (prod) => {
    setCarrito((prev) => {
      const existe = prev.find((item) => item.producto_id === prod.id)
      if (existe) {
        return prev.map((item) =>
          item.producto_id === prod.id ? { ...item, cantidad: item.cantidad + 1 } : item
        )
      }
      return [...prev, { producto_id: prod.id, nombre: prod.nombre, precio: prod.precio_base, cantidad: 1 }]
    })
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
        items: carrito.map((item) => ({
          producto_id: item.producto_id,
          cantidad: item.cantidad,
          adiciones: [],
          exclusiones: [],
          observaciones: '',
        })),
      }

      const res = await crearPedidoOperador(payload)
      setMensaje({ tipo: 'exito', texto: `¡Pedido #${res.numero_pedido} registrado con éxito!` })
      setCarrito([])
    } catch (err) {
      console.error('Error backend 400:', err.response?.data)
      const detalleError = err.response?.data
        ? JSON.stringify(err.response.data)
        : 'Error al registrar el pedido.'
      setMensaje({ tipo: 'error', texto: `Error: ${detalleError}` })
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
              onClick={() => agregarAlCarrito(prod)}
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
            <div key={item.producto_id} className="flex justify-between text-sm">
              <span>{item.cantidad}x {item.nombre}</span>
              <span>{formatearPrecio(item.precio * item.cantidad)}</span>
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
          disabled={cargando || carrito.length === 0}
          onClick={handleSubmit}
        >
          {cargando ? 'Procesando...' : 'Confirmar Pedido'}
        </Boton>
      </div>
    </div>
  )
}