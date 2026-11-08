import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { useCarrito } from '../../carrito/useCarrito.js'
import { confirmarPedidoCliente } from '../../api/pedidos.js'
import { obtenerDireccionesCliente } from '../../api/direcciones.js'
import Boton from '../../components/ui/Boton.jsx'
import Alerta from '../../components/ui/Alerta.jsx'
import { formatearPrecio } from '../../utils/formato.js'
import { subtotalLinea } from '../../utils/carrito.js'
import { validarCoberturaDireccion } from '../../api/sedes.js'

export default function ConfirmarPedido() {
  const navigate = useNavigate()

  // Hook del carrito con las propiedades reales de tu context
  const { sedeId, lineas = [], subtotal, costoDomicilio, total, vaciar } = useCarrito()

  const [direcciones, setDirecciones] = useState([])
  const [direccionId, setDireccionId] = useState('')
  const [metodoPago, setMetodoPago] = useState('efectivo')
  const [observaciones, setObservaciones] = useState('')

  const [cargando, setCargando] = useState(false)
  const [mensaje, setMensaje] = useState(null)
  const [erroresItems, setErroresItems] = useState([])
  const [resumenExito, setResumenExito] = useState(null)
  const [coberturaInfo, setCoberturaInfo] = useState(null)
  const [validandoCobertura, setValidandoCobertura] = useState(false)

  const handleSeleccionarDireccion = async (dirObj) => {
    setDireccionId(dirObj.id)
    setMensaje(null)

    if (dirObj.latitud && dirObj.longitud) {
      setValidandoCobertura(true)
      try {
        const res = await validarCoberturaDireccion(dirObj.latitud, dirObj.longitud)
        setCoberturaInfo(res)
        if (!res.cubierto) {
          setMensaje({ tipo: 'error', texto: res.mensaje })
        }
      } catch {
        setMensaje({ tipo: 'error', texto: 'No se pudo verificar la cobertura de la dirección.' })
      } finally {
        setValidandoCobertura(false)
      }
    }
  }

  useEffect(() => {
    obtenerDireccionesCliente()
      .then((data) => {
        const lista = Array.isArray(data) ? data : data?.results || []
        setDirecciones(lista)
        if (lista.length > 0) setDireccionId(lista[0].id)
      })
      .catch((err) => console.error('Error al cargar direcciones:', err))
  }, [])

  const handleSubmit = async (e) => {
    e.preventDefault()
    setMensaje(null)
    setErroresItems([])

    // Validar sedeId del context (o fallback del localStorage)
    const sedeFinal = sedeId || localStorage.getItem('domipedidosx.sede')

    if (!sedeFinal) {
      setMensaje({
        tipo: 'error',
        texto: 'No se detectó una sede seleccionada. Regresa al menú para seleccionar tu sede.',
      })
      return
    }

    if (!direccionId) {
      setMensaje({ tipo: 'error', texto: 'Por favor selecciona una dirección de entrega.' })
      return
    }

    if (!lineas || lineas.length === 0) {
      setMensaje({ tipo: 'error', texto: 'El carrito está vacío.' })
      return
    }

    try {
      setCargando(true)

      // Payload mapeado a la estructura exacta exigida por Django
      const payload = {
        sede_id: Number(sedeFinal),
        direccion_id: Number(direccionId),
        metodo_pago: metodoPago,
        observaciones: observaciones.trim(),
        items: lineas.map((linea) => {
          // Si la línea corresponde a un combo
          if (linea.combo || linea.combo_id) {
            return {
              combo_id: Number(linea.combo_id || linea.combo?.id || linea.id),
              cantidad: Number(linea.cantidad || 1),
            }
          }

          // Mapeo seguro de adiciones buscando la propiedad ID en todas sus variaciones
          const adicionesMapeadas = (linea.adiciones || [])
            .map((ad) => {
              const idReal = ad.adicion_id ?? ad.id ?? (typeof ad.adicion === 'object' ? ad.adicion?.id : ad.adicion)
              return {
                adicion_id: Number(idReal),
                cantidad: Number(ad.cantidad || 1),
              }
            })
            .filter((ad) => !isNaN(ad.adicion_id) && ad.adicion_id > 0)

          // Mapeo seguro de exclusiones
          const exclusionesMapeadas = (linea.exclusiones || [])
            .map((ex) => {
              const idReal = ex.exclusion_id ?? ex.id ?? (typeof ex.exclusion === 'object' ? ex.exclusion?.id : ex)
              return Number(idReal)
            })
            .filter((id) => !isNaN(id) && id > 0)

          return {
            producto_id: Number(linea.producto?.id || linea.producto_id || linea.id),
            ...(linea.tamano?.id && { tamano_id: Number(linea.tamano.id) }),
            cantidad: Number(linea.cantidad || 1),
            adiciones: adicionesMapeadas,
            exclusiones: exclusionesMapeadas,
            observaciones: linea.observaciones || '',
          }
        }),
      }

      const res = await confirmarPedidoCliente(payload)
      setResumenExito(res)

      // Vaciar el carrito usando la función nativa del contexto
      if (typeof vaciar === 'function') {
        vaciar()
      }
    } catch (err) {
      console.error('Error al confirmar pedido:', err.response?.data)
      const dataError = err.response?.data
      const status = err.response?.status

      if (status === 403) {
        setMensaje({ tipo: 'error', texto: 'Solo los clientes pueden realizar pedidos.' })
      } else if (status === 400 && dataError?.items) {
        if (Array.isArray(dataError.items)) {
          setMensaje({ tipo: 'error', texto: dataError.detail || 'Algunos ítems no están disponibles.' })
          setErroresItems(dataError.items)
        } else if (typeof dataError.items === 'object') {
          const listaErrores = Object.entries(dataError.items).map(([indice, detalles]) => {
            const msgs = Object.entries(detalles)
              .map(([campo, msgs]) => `${campo}: ${Array.isArray(msgs) ? msgs.join(', ') : msgs}`)
              .join(' | ')
            return {
              indice: Number(indice),
              nombre: lineas[Number(indice)]?.producto?.nombre || `Ítem #${Number(indice) + 1}`,
              motivo: msgs,
            }
          })
          setMensaje({ tipo: 'error', texto: 'Revisa los errores en los productos del carrito.' })
          setErroresItems(listaErrores)
        }
      } else if (typeof dataError === 'object' && dataError !== null) {
        const textoError = Object.entries(dataError)
          .map(([k, v]) => `${k}: ${Array.isArray(v) ? v.join(', ') : typeof v === 'object' ? JSON.stringify(v) : v}`)
          .join(' | ')
        setMensaje({ tipo: 'error', texto: textoError })
      } else {
        setMensaje({ tipo: 'error', texto: 'Error inesperado al procesar el pedido.' })
      }
    } finally {
      setCargando(false)
    }
  }

  // Vista de pedido exitoso tras el 201 Created
  if (resumenExito) {
    return (
      <div className="mx-auto max-w-xl space-y-4 rounded-xl border border-borde bg-superficie p-6 text-center shadow-sm">
        <div className="inline-flex h-12 w-12 items-center justify-center rounded-full bg-verde/10 text-2xl font-bold text-verde">
          ✓
        </div>
        <h1 className="text-2xl font-bold">¡Pedido Confirmado!</h1>
        <p className="text-texto-suave">
          Número de Pedido: <strong className="text-texto">#{resumenExito.numero_pedido}</strong>
        </p>
        <p className="text-sm">
          Estado: <span className="font-semibold uppercase text-marca">{resumenExito.estado}</span>
        </p>
        {resumenExito.tiempo_estimado_entrega && (
          <p className="text-sm">
            Tiempo estimado de entrega: <strong>{resumenExito.tiempo_estimado_entrega} mins</strong>
          </p>
        )}

        {resumenExito.factura && (
          <div className="mt-4 space-y-2 rounded-lg border border-borde bg-fondo p-4 text-left">
            <h3 className="border-b border-borde pb-2 font-bold">Resumen de Factura</h3>
            <div className="flex justify-between text-sm">
              <span>Subtotal:</span>
              <span>{formatearPrecio(resumenExito.factura.subtotal)}</span>
            </div>
            {resumenExito.factura.costo_domicilio > 0 && (
              <div className="flex justify-between text-sm">
                <span>Domicilio:</span>
                <span>{formatearPrecio(resumenExito.factura.costo_domicilio)}</span>
              </div>
            )}
            <div className="flex justify-between border-t border-borde pt-2 text-base font-bold text-marca">
              <span>Total pagado:</span>
              <span>{formatearPrecio(resumenExito.factura.total)}</span>
            </div>
          </div>
        )}

        <Boton variante="primario" className="mt-4 w-full" onClick={() => navigate('/pedidos')}>
          Ver mis pedidos
        </Boton>
      </div>
    )
  }

  return (
    <div className="mx-auto max-w-2xl space-y-6 rounded-xl border border-borde bg-superficie p-6 shadow-sm">
      <h1 className="text-2xl font-bold">Confirmar Pedido</h1>

      {mensaje && <Alerta tipo={mensaje.tipo} titulo={mensaje.texto} />}

      {erroresItems.length > 0 && (
        <div className="space-y-1 rounded-lg border border-rojo bg-rojo/10 p-4 text-sm text-rojo">
          <p className="font-bold">Ítems con inconvenientes:</p>
          <ul className="list-disc pl-5">
            {erroresItems.map((err, idx) => (
              <li key={idx}>
                {err.nombre ? <strong>{err.nombre}: </strong> : `Ítem #${err.indice + 1}: `}
                {err.motivo}
              </li>
            ))}
          </ul>
        </div>
      )}

      <form onSubmit={handleSubmit} className="space-y-4">
        {/* Dirección de Entrega */}
        <div>
          <label className="mb-1 block text-sm font-semibold">Dirección de Entrega</label>
          {direcciones.length === 0 ? (
            <p className="text-sm text-texto-suave">
              No tienes direcciones registradas.{' '}
              <button
                type="button"
                onClick={() => navigate('/perfil/direcciones')}
                className="text-marca underline"
              >
                Agregar una dirección
              </button>
            </p>
          ) : (
            <select
              value={direccionId}
              onChange={(e) => setDireccionId(e.target.value)}
              required
              className="w-full rounded-lg border border-borde bg-fondo p-2.5 text-texto"
            >
              {direcciones.map((dir) => (
                <option key={dir.id} value={dir.id}>
                  {dir.direccion} {dir.barrio ? `(${dir.barrio})` : ''}
                </option>
              ))}
            </select>
          )}
        </div>

        {/* Método de Pago */}
        <div>
          <label className="mb-1 block text-sm font-semibold">Método de Pago</label>
          <select
            value={metodoPago}
            onChange={(e) => setMetodoPago(e.target.value)}
            className="w-full rounded-lg border border-borde bg-fondo p-2.5 text-texto"
          >
            <option value="efectivo">Efectivo</option>
            <option value="tarjeta">Tarjeta (Simulado)</option>
            <option value="transferencia">Transferencia (Simulado)</option>
          </select>
        </div>

        {/* Observaciones */}
        <div>
          <label className="mb-1 block text-sm font-semibold">Observaciones / Indicaciones de entrega</label>
          <textarea
            rows={3}
            placeholder="Ej: Sin timbre, llamar al llegar, apartamento 302..."
            value={observaciones}
            onChange={(e) => setObservaciones(e.target.value)}
            className="w-full rounded-lg border border-borde bg-fondo p-2.5 text-texto"
          />
        </div>

        {/* Resumen de Ítems */}
        <div className="space-y-2 rounded-lg border border-borde bg-fondo p-4">
          <h3 className="text-sm font-semibold">Resumen de Ítems ({lineas.length})</h3>
          <ul className="divide-y divide-borde text-sm">
            {lineas.map((linea) => (
              <li key={linea.id} className="flex justify-between py-2">
                <div>
                  <span className="font-medium">
                    {linea.cantidad}x {linea.producto?.nombre || 'Producto'}
                  </span>
                  {linea.tamano?.nombre && (
                    <span className="text-xs text-texto-suave"> ({linea.tamano.nombre})</span>
                  )}
                </div>
                <span className="font-semibold">{formatearPrecio(subtotalLinea(linea))}</span>
              </li>
            ))}
          </ul>

          <div className="flex justify-between text-xs text-texto-suave pt-2 border-t border-borde">
            <span>Subtotal:</span>
            <span>{formatearPrecio(subtotal)}</span>
          </div>
          {costoDomicilio > 0 && (
            <div className="flex justify-between text-xs text-texto-suave">
              <span>Domicilio:</span>
              <span>{formatearPrecio(costoDomicilio)}</span>
            </div>
          )}

          <div className="flex items-center justify-between pt-2 border-t border-borde text-base font-bold">
            <span>Total estimado:</span>
            <span className="text-marca">{formatearPrecio(total)}</span>
          </div>
        </div>

        <Boton
          tipo="submit"
          variante="primario"
          className="mt-4 w-full"
          disabled={cargando || !direccionId}
        >
          {cargando ? 'Procesando pedido...' : 'Confirmar y Pagar'}
        </Boton>
      </form>
    </div>
  )
}