import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { interpretarError } from '../../api/errores.js'
import { listarMisPedidos, repetirPedido } from '../../api/pedidos.js'
import { useCarrito } from '../../carrito/useCarrito.js'
import Alerta from '../../components/ui/Alerta.jsx'
import Boton from '../../components/ui/Boton.jsx'
import Tarjeta from '../../components/ui/Tarjeta.jsx'
import { datosEstado } from '../../utils/estadosPedido.js'
import { formatearPrecio } from '../../utils/formato.js'
import { avisoRepetir, puedeRepetirse } from '../../utils/repetirPedido.js'
import { guardarSede } from '../../utils/sedeElegida.js'
import { horaCorta } from '../../utils/tiempo.js'

const CERRADOS = ['entregado', 'cancelado']

function TarjetaPedidoCliente({ pedido, repitiendo, alRepetir }) {
  const estado = datosEstado(pedido.estado)
  const fecha = new Date(pedido.fecha_creacion).toLocaleDateString('es-CO', { day: 'numeric', month: 'short' })
  return (
    <li className="flex flex-col rounded-xl border border-borde bg-fondo transition-colors hover:border-texto-suave">
      <Link
        to={`/mis-pedidos/${pedido.id}`}
        aria-label={`Seguir el pedido ${pedido.numero_pedido}`}
        className="flex flex-col gap-2 rounded-xl p-3"
      >
        <div className="flex flex-wrap items-start justify-between gap-2">
          <div>
            <p className="font-bold">{pedido.numero_pedido}</p>
            <p className="text-sm text-texto-suave">
              {fecha} · {horaCorta(pedido.fecha_creacion)}
            </p>
          </div>
          <span className={`rounded-full border px-2 py-0.5 text-xs font-medium ${estado.clases}`}>
            {estado.etiqueta}
          </span>
        </div>
        {pedido.resumen.length > 0 && <p className="text-sm">{pedido.resumen.join(', ')}</p>}
        <div className="flex flex-wrap items-center justify-between gap-2 text-sm">
          <span className="font-semibold">{pedido.total ? formatearPrecio(pedido.total) : ''}</span>
          <span aria-hidden="true" className="text-marca-clara">
            {CERRADOS.includes(pedido.estado) ? 'Ver detalle →' : 'Seguir pedido →'}
          </span>
        </div>
      </Link>
      {alRepetir && (
        <div className="border-t border-borde px-3 py-2">
          <Boton
            variante="secundario"
            cargando={repitiendo}
            onClick={() => alRepetir(pedido)}
            aria-label={`Repetir el pedido ${pedido.numero_pedido}`}
          >
            Repetir pedido
          </Boton>
        </div>
      )}
    </li>
  )
}

// HU-47 · Orders of the customer, the ones in progress first, each one opens its live tracking
// HU-26 · The closed ones can be repeated: their products go back to the cart at today's prices
export default function MisPedidos() {
  const [pedidos, setPedidos] = useState(null)
  const [error, setError] = useState(null)
  const [repitiendo, setRepitiendo] = useState(null)
  const [aviso, setAviso] = useState(null)
  const carrito = useCarrito()

  async function repetir(pedido) {
    setAviso(null)
    setRepitiendo(pedido.id)
    try {
      const respuesta = await repetirPedido(pedido.id)
      const resultado = avisoRepetir(pedido.numero_pedido, respuesta)
      if (resultado.hayLineas) {
        const reemplazar =
          carrito.articulos === 0 ||
          window.confirm('Tu carrito ya tiene productos. ¿Quieres reemplazarlos por los de este pedido?')
        if (!reemplazar) return
        carrito.cargarPedido(respuesta.sede.id, respuesta.lineas)
        guardarSede(respuesta.sede.id)
      }
      setAviso(resultado)
    } catch (fallo) {
      setAviso({ tipo: 'error', titulo: interpretarError(fallo).general, faltantes: [], hayLineas: false })
    } finally {
      setRepitiendo(null)
      window.scrollTo?.({ top: 0, behavior: 'smooth' })
    }
  }

  useEffect(() => {
    let vigente = true
    listarMisPedidos()
      .then((datos) => {
        if (vigente) setPedidos(datos)
      })
      .catch((fallo) => {
        if (vigente) setError(interpretarError(fallo).general)
      })
    return () => {
      vigente = false
    }
  }, [])

  const enCurso = pedidos?.filter((pedido) => !CERRADOS.includes(pedido.estado)) ?? []
  const anteriores = pedidos?.filter((pedido) => CERRADOS.includes(pedido.estado)) ?? []

  return (
    <div className="flex flex-col gap-4">
      <header>
        <h1 className="text-2xl font-bold">Mis pedidos</h1>
        <p className="text-texto-suave">
          Toca un pedido para seguirlo en tiempo real. Los anteriores los puedes repetir.
        </p>
      </header>

      {error && <Alerta tipo="error" titulo={error} />}
      {aviso && (
        <Alerta tipo={aviso.tipo} titulo={aviso.titulo}>
          {aviso.faltantes.length > 0 && (
            <>
              <p>No se agregaron porque hoy no están disponibles:</p>
              <ul className="list-disc pl-5">
                {aviso.faltantes.map((faltante) => (
                  <li key={faltante.nombre}>
                    {faltante.nombre}: {faltante.motivo}
                  </li>
                ))}
              </ul>
            </>
          )}
          {aviso.hayLineas && (
            <Link to="/carrito" className="font-semibold text-marca-clara underline underline-offset-4">
              Ir al carrito
            </Link>
          )}
        </Alerta>
      )}
      {!pedidos && !error && <p className="text-texto-suave">Cargando…</p>}
      {pedidos?.length === 0 && (
        <Alerta tipo="info" titulo="Todavía no tienes pedidos">
          <Link to="/menu" className="text-marca-clara underline underline-offset-4">
            Ir al menú
          </Link>
        </Alerta>
      )}

      {enCurso.length > 0 && (
        <Tarjeta titulo="En curso">
          <ul className="flex flex-col gap-3">
            {enCurso.map((pedido) => (
              <TarjetaPedidoCliente key={pedido.id} pedido={pedido} />
            ))}
          </ul>
        </Tarjeta>
      )}
      {anteriores.length > 0 && (
        <Tarjeta titulo="Anteriores">
          <ul className="flex flex-col gap-3">
            {anteriores.map((pedido) => (
              <TarjetaPedidoCliente
                key={pedido.id}
                pedido={pedido}
                repitiendo={repitiendo === pedido.id}
                alRepetir={puedeRepetirse(pedido) ? repetir : null}
              />
            ))}
          </ul>
        </Tarjeta>
      )}
    </div>
  )
}
