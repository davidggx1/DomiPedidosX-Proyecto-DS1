import { useEffect, useState } from 'react'
import { interpretarError } from '../../api/errores.js'
import { obtenerFichaPedido } from '../../api/pedidos.js'
import { datosEstado } from '../../utils/estadosPedido.js'
import { formatearPrecio } from '../../utils/formato.js'
import { autorDelPaso } from '../../utils/historial.js'
import { fechaHora, textoDuracion } from '../../utils/tiempo.js'
import Alerta from '../ui/Alerta.jsx'

function Dato({ etiqueta, children }) {
  return (
    <div>
      <dt className="text-sm text-texto-suave">{etiqueta}</dt>
      <dd className="break-words">{children}</dd>
    </div>
  )
}

const METODOS = { efectivo: 'Efectivo', tarjeta: 'Tarjeta', transferencia: 'Transferencia' }

// HU-66 · Ficha técnica de un pedido: cada cambio de estado con su hora,
// quién lo hizo y cuánto tardó desde el paso anterior. Va dentro de un Modal.
export default function FichaPedido({ id }) {
  const [ficha, setFicha] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    let vigente = true
    obtenerFichaPedido(id)
      .then((datos) => vigente && setFicha(datos))
      .catch((fallo) => vigente && setError(interpretarError(fallo).general))
    return () => {
      vigente = false
    }
  }, [id])

  if (error) return <Alerta tipo="error" titulo={error} />
  if (!ficha) return <p className="text-texto-suave">Cargando ficha…</p>

  const estado = datosEstado(ficha.estado)

  return (
    <div className="flex flex-col gap-5">
      {ficha.estado === 'cancelado' && (
        <Alerta tipo="error" titulo="Pedido cancelado">
          {ficha.motivo_cancelacion || 'Sin motivo registrado.'}
        </Alerta>
      )}

      <section>
        <dl className="grid gap-3 sm:grid-cols-2">
          <Dato etiqueta="Estado">
            <span className={`rounded-full border px-2 py-0.5 text-sm font-medium ${estado.clases}`}>
              {estado.etiqueta}
            </span>
          </Dato>
          <Dato etiqueta="Creado">{fechaHora(ficha.fecha_creacion)}</Dato>
          <Dato etiqueta="Sede">{ficha.sede.nombre}</Dato>
          <Dato etiqueta="Cliente">{ficha.cliente ?? 'Sin cliente registrado'}</Dato>
          {ficha.entrega_direccion && (
            <Dato etiqueta="Entrega">
              {ficha.entrega_direccion}
              {ficha.entrega_barrio && `, ${ficha.entrega_barrio}`}
            </Dato>
          )}
          <Dato etiqueta="Repartidor">
            {ficha.repartidor
              ? `${ficha.repartidor}${ficha.asignacion_automatica ? ' (asignación automática)' : ''}`
              : 'Sin asignar'}
          </Dato>
        </dl>
      </section>

      <section>
        <h3 className="mb-2 font-semibold">Cambios de estado</h3>
        {ficha.historial.length === 0 ? (
          <p className="text-sm text-texto-suave">Este pedido no tiene cambios de estado registrados.</p>
        ) : (
          <ol className="flex flex-col gap-3 border-l-2 border-borde pl-4">
            {ficha.historial.map((paso, indice) => (
              <li key={`${paso.estado}-${indice}`} className="relative">
                <span aria-hidden="true" className="absolute top-1.5 -left-[1.4rem] size-3 rounded-full bg-marca" />
                <p className="font-medium">{paso.estado_nombre}</p>
                <p className="text-sm text-texto-suave">
                  {fechaHora(paso.fecha_hora)} · {autorDelPaso(paso)}
                  {paso.minutos_desde_anterior != null && ` · ${textoDuracion(paso.minutos_desde_anterior)} después`}
                </p>
                {paso.observacion && <p className="text-sm">{paso.observacion}</p>}
              </li>
            ))}
          </ol>
        )}
      </section>

      {ficha.detalles.length > 0 && (
        <section>
          <h3 className="mb-2 font-semibold">Productos</h3>
          <ul className="flex flex-col gap-1 text-sm">
            {ficha.detalles.map((linea, indice) => (
              <li key={indice}>
                {linea.cantidad}× {linea.nombre}
                {linea.tamano && ` · ${linea.tamano}`}
                {linea.adiciones.length > 0 &&
                  ` · + ${linea.adiciones.map((adicion) => adicion.nombre).join(', ')}`}
                {linea.sin.length > 0 && ` · sin ${linea.sin.join(', ')}`}
              </li>
            ))}
          </ul>
        </section>
      )}

      {ficha.factura && (
        <section>
          <h3 className="mb-2 font-semibold">Factura {ficha.factura.numero}</h3>
          <dl className="grid gap-x-6 gap-y-1 text-sm sm:grid-cols-2">
            <Dato etiqueta="Método de pago">{METODOS[ficha.factura.metodo_pago] ?? ficha.factura.metodo_pago}</Dato>
            <Dato etiqueta="Subtotal">{formatearPrecio(ficha.factura.subtotal)}</Dato>
            <Dato etiqueta="Domicilio">{formatearPrecio(ficha.factura.costo_domicilio)}</Dato>
            {Number(ficha.factura.valor_descuento) > 0 && (
              <Dato etiqueta="Descuento">−{formatearPrecio(ficha.factura.valor_descuento)}</Dato>
            )}
            <Dato etiqueta="Total">
              <strong>{formatearPrecio(ficha.factura.total)}</strong>
            </Dato>
          </dl>
        </section>
      )}
    </div>
  )
}
