import { useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { interpretarError } from '../../api/errores.js'
import { conectarMisEntregas, obtenerEntrega } from '../../api/repartidores.js'
import DetalleComanda from '../../components/cocina/DetalleComanda.jsx'
import ConfirmarPasoEntrega from '../../components/repartidor/ConfirmarPasoEntrega.jsx'
import Alerta from '../../components/ui/Alerta.jsx'
import Boton from '../../components/ui/Boton.jsx'
import Tarjeta from '../../components/ui/Tarjeta.jsx'
import { avanceDeEntrega, avisoDePago, enlaceMapa } from '../../utils/entregas.js'
import { datosEstado } from '../../utils/estadosPedido.js'
import { formatearPrecio } from '../../utils/formato.js'

const ESTILO_BANNER = {
  aviso: 'border-aviso bg-aviso/15 text-aviso',
  exito: 'border-exito bg-exito/15 text-exito',
  info: 'border-borde bg-superficie-alta text-texto',
}

// Big banner so the repartidor never misses if he has to charge (HU-43)
function BannerPago({ entrega }) {
  const aviso = avisoDePago(entrega)
  return (
    <div role="status" className={`rounded-xl border-2 px-4 py-3 ${ESTILO_BANNER[aviso.tipo]}`}>
      <p className="text-xl font-bold">{aviso.titulo}</p>
      <p className="text-texto">{aviso.texto}</p>
    </div>
  )
}

function Fila({ nombre, valor, destacado = false }) {
  return (
    <div className={`flex justify-between gap-4 ${destacado ? 'font-bold' : ''}`}>
      <dt className={destacado ? '' : 'text-texto-suave'}>{nombre}</dt>
      <dd>{valor}</dd>
    </div>
  )
}

const VOLVER = (
  <Link to="/repartidor" className="self-start text-marca-clara underline underline-offset-4">
    ← Volver a mis entregas
  </Link>
)

// HU-43 · Delivery order: where to go, what to bring and how much to charge.
// HU-45 · The button that moves the delivery one step forward, after confirming
export default function DetalleEntrega() {
  const { id } = useParams()
  const [entrega, setEntrega] = useState(null)
  const [error, setError] = useState(null)
  const [yaNoEsTuya, setYaNoEsTuya] = useState(false)
  const [confirmando, setConfirmando] = useState(false)
  const [mensaje, setMensaje] = useState(null)
  const navegar = useNavigate()

  useEffect(() => {
    let vigente = true

    function cargar() {
      obtenerEntrega(id)
        .then((datos) => {
          if (!vigente) return
          setEntrega(datos)
          setError(null)
        })
        .catch((fallo) => {
          if (!vigente) return
          // 404: it was removed from him, delivered or cancelled
          if (fallo.response?.status === 404) setYaNoEsTuya(true)
          else setError(interpretarError(fallo).general)
        })
    }

    cargar()
    // if the operator removes the order or it is cancelled, the page finds out
    const cerrar = conectarMisEntregas({
      alMensaje: (aviso) => {
        if (String(aviso.pedido_id) === id) cargar()
      },
      alReconectar: cargar,
    })
    return () => {
      vigente = false
      cerrar()
    }
  }, [id])

  if (yaNoEsTuya) {
    return (
      <div className="flex flex-col gap-4">
        {VOLVER}
        <Alerta tipo="info" titulo="Esta entrega ya no está en tu lista">
          Pudo haberse entregado, cancelado o asignado a otro repartidor.
        </Alerta>
      </div>
    )
  }

  if (!entrega) {
    return (
      <div className="flex flex-col gap-4">
        {VOLVER}
        {error ? <Alerta tipo="error" titulo={error} /> : <p className="text-texto-suave">Cargando…</p>}
      </div>
    )
  }

  const estado = datosEstado(entrega.estado)
  const avance = avanceDeEntrega(entrega)

  function pasoConfirmado(actualizada) {
    setConfirmando(false)
    if (actualizada.estado === 'entregado') {
      // the order is closed: it leaves the list, back to the remaining deliveries
      navegar('/repartidor', { state: { mensaje: `Pedido ${actualizada.numero_pedido} entregado.` } })
      return
    }
    setEntrega(actualizada)
    setMensaje(`Pedido ${actualizada.numero_pedido}: ${datosEstado(actualizada.estado).etiqueta.toLowerCase()}.`)
  }

  return (
    <div className="flex flex-col gap-4">
      {VOLVER}

      <header className="flex flex-wrap items-center justify-between gap-2">
        <h1 className="text-2xl font-bold">Pedido {entrega.numero_pedido}</h1>
        <span className={`rounded-full border px-3 py-1 text-sm font-medium ${estado.clases}`}>
          {estado.etiqueta}
        </span>
      </header>

      {error && <Alerta tipo="error" titulo={error} />}
      {mensaje && <Alerta tipo="exito" titulo={mensaje} />}
      <BannerPago entrega={entrega} />

      {avance && (
        <Boton onClick={() => setConfirmando(true)} className="w-full text-lg">
          {avance.texto}
        </Boton>
      )}
      {confirmando && (
        <ConfirmarPasoEntrega
          entrega={entrega}
          avance={avance}
          alCerrar={() => setConfirmando(false)}
          alConfirmar={pasoConfirmado}
        />
      )}

      <Tarjeta titulo="Dirección de entrega">
        <div className="flex flex-col gap-1">
          {entrega.entrega_alias && <p className="text-sm text-texto-suave">{entrega.entrega_alias}</p>}
          <p className="font-medium">{entrega.entrega_direccion || 'Sin dirección registrada'}</p>
          {entrega.entrega_barrio && <p>{entrega.entrega_barrio}</p>}
          {entrega.entrega_indicaciones && (
            <p className="text-sm">
              <span className="text-texto-suave">Indicaciones: </span>
              {entrega.entrega_indicaciones}
            </p>
          )}
          <a
            href={enlaceMapa(entrega)}
            target="_blank"
            rel="noreferrer"
            className="mt-2 self-start text-marca-clara underline underline-offset-4"
          >
            Abrir en el mapa
          </a>
        </div>
      </Tarjeta>

      <Tarjeta titulo="Cliente">
        {entrega.cliente ? (
          <div className="flex flex-col gap-1">
            <p className="font-medium">{entrega.cliente.nombre}</p>
            <a href={`tel:${entrega.cliente.celular}`} className="self-start text-marca-clara underline underline-offset-4">
              Llamar al {entrega.cliente.celular}
            </a>
          </div>
        ) : (
          <p className="text-texto-suave">Cliente sin registrar. Pide los datos de contacto al operador.</p>
        )}
      </Tarjeta>

      <Tarjeta>
        <DetalleComanda comanda={entrega} />
      </Tarjeta>

      {entrega.total && (
        <Tarjeta titulo="Totales">
          <dl className="flex flex-col gap-1">
            <Fila nombre="Subtotal" valor={formatearPrecio(entrega.subtotal)} />
            <Fila nombre="Domicilio" valor={formatearPrecio(entrega.costo_domicilio)} />
            {Number(entrega.valor_descuento) > 0 && (
              <Fila nombre="Descuento" valor={`− ${formatearPrecio(entrega.valor_descuento)}`} />
            )}
            <Fila nombre="Total" valor={formatearPrecio(entrega.total)} destacado />
            <Fila nombre="Método de pago" valor={entrega.metodo_pago_nombre} />
          </dl>
        </Tarjeta>
      )}
    </div>
  )
}
