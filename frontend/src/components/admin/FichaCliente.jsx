import { useEffect, useState } from 'react'
import { obtenerFichaCliente } from '../../api/clientes.js'
import { interpretarError } from '../../api/errores.js'
import { datosEstado } from '../../utils/estadosPedido.js'
import { formatearPrecio } from '../../utils/formato.js'
import { fechaCorta, fechaHora } from '../../utils/tiempo.js'
import Alerta from '../ui/Alerta.jsx'

function Dato({ etiqueta, children }) {
  return (
    <div>
      <dt className="text-sm text-texto-suave">{etiqueta}</dt>
      <dd className="break-words">{children}</dd>
    </div>
  )
}

// HU-69 · Ficha del cliente: contacto, estado de la cuenta y todo su historial
// de pedidos. Va dentro de un Modal en la página de Clientes.
export default function FichaCliente({ id }) {
  const [ficha, setFicha] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    let vigente = true
    obtenerFichaCliente(id)
      .then((datos) => vigente && setFicha(datos))
      .catch((fallo) => vigente && setError(interpretarError(fallo).general))
    return () => {
      vigente = false
    }
  }, [id])

  if (error) return <Alerta tipo="error" titulo={error} />
  if (!ficha) return <p className="text-texto-suave">Cargando ficha…</p>

  return (
    <div className="flex flex-col gap-5">
      <section>
        <h3 className="mb-2 font-semibold">Datos de contacto</h3>
        <dl className="grid gap-3 sm:grid-cols-2">
          <Dato etiqueta="Correo">{ficha.email}</Dato>
          <Dato etiqueta="Celular">{ficha.celular}</Dato>
          <Dato etiqueta="Documento">
            {ficha.tipo_documento} {ficha.num_documento}
          </Dato>
          <Dato etiqueta="Fecha de nacimiento">{fechaCorta(`${ficha.fecha_nacimiento}T00:00:00`)}</Dato>
          <Dato etiqueta="Estado de la cuenta">
            <span className={ficha.activa ? 'text-exito' : 'text-aviso'}>
              {ficha.activa ? 'Activa' : 'Desactivada'}
            </span>
          </Dato>
          <Dato etiqueta="Registrado el">{fechaCorta(ficha.fecha_registro)}</Dato>
        </dl>
        {ficha.direcciones.length > 0 && (
          <div className="mt-3">
            <p className="text-sm text-texto-suave">Direcciones</p>
            <ul className="mt-1 flex flex-col gap-1">
              {ficha.direcciones.map((direccion) => (
                <li key={direccion.id} className="text-sm">
                  {direccion.alias && <span className="font-medium">{direccion.alias}: </span>}
                  {direccion.direccion}
                  {direccion.barrio && `, ${direccion.barrio}`}
                  {direccion.es_principal && <span className="text-texto-suave"> (principal)</span>}
                </li>
              ))}
            </ul>
          </div>
        )}
      </section>

      <section>
        <h3 className="mb-2 font-semibold">Historial de pedidos ({ficha.pedidos.length})</h3>
        {ficha.pedidos.length === 0 ? (
          <p className="text-texto-suave">Este cliente todavía no ha hecho pedidos.</p>
        ) : (
          <ul className="flex flex-col gap-2">
            {ficha.pedidos.map((pedido) => {
              const estado = datosEstado(pedido.estado)
              return (
                <li key={pedido.id} className="rounded-lg border border-borde bg-fondo px-3 py-2">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <p className="font-medium">{pedido.numero_pedido}</p>
                    <span className={`rounded-full border px-2 py-0.5 text-xs font-medium ${estado.clases}`}>
                      {estado.etiqueta}
                    </span>
                  </div>
                  <p className="text-sm text-texto-suave">
                    {fechaHora(pedido.fecha_creacion)} · {pedido.sede} · {pedido.origen_nombre}
                  </p>
                  <p className="text-sm">{pedido.resumen.join(', ')}</p>
                  <p className="text-sm text-texto-suave">
                    {pedido.total !== null ? formatearPrecio(pedido.total) : 'Sin factura'}
                    {pedido.metodo_pago && ` · ${pedido.metodo_pago}`}
                    {pedido.entrega_direccion && ` · ${pedido.entrega_direccion}`}
                  </p>
                  {pedido.motivo_cancelacion && (
                    <p className="text-sm text-error">Motivo: {pedido.motivo_cancelacion}</p>
                  )}
                </li>
              )
            })}
          </ul>
        )}
      </section>
    </div>
  )
}
