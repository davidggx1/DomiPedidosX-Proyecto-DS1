import { useCallback, useEffect, useState } from 'react'
import { buscarClientes } from '../../api/clientes.js'
import { interpretarError } from '../../api/errores.js'
import FichaCliente from '../../components/admin/FichaCliente.jsx'
import Alerta from '../../components/ui/Alerta.jsx'
import Boton from '../../components/ui/Boton.jsx'
import CampoTexto from '../../components/ui/CampoTexto.jsx'
import Modal from '../../components/ui/Modal.jsx'
import Tarjeta from '../../components/ui/Tarjeta.jsx'
import { fechaCorta } from '../../utils/tiempo.js'

// HU-69 · Información de clientes (vista del administrador).
// Busca por nombre, correo o teléfono y abre la ficha con el historial de pedidos.
export default function Clientes() {
  const [texto, setTexto] = useState('')
  const [buscado, setBuscado] = useState('')
  const [clientes, setClientes] = useState([])
  const [cargando, setCargando] = useState(true)
  const [error, setError] = useState(null)
  const [seleccionado, setSeleccionado] = useState(null)

  useEffect(() => {
    let vigente = true
    buscarClientes(buscado)
      .then((datos) => {
        if (!vigente) return
        setClientes(datos)
        setError(null)
      })
      .catch((fallo) => {
        if (vigente) setError(interpretarError(fallo).general)
      })
      .finally(() => {
        if (vigente) setCargando(false)
      })
    return () => {
      vigente = false
    }
  }, [buscado])

  const cerrarFicha = useCallback(() => setSeleccionado(null), [])

  function buscar(evento) {
    evento.preventDefault()
    setCargando(true)
    setBuscado(texto.trim())
  }

  function limpiar() {
    setTexto('')
    if (buscado) {
      setCargando(true)
      setBuscado('')
    }
  }

  return (
    <div className="flex flex-col gap-6">
      <header>
        <h1 className="text-2xl font-bold">Clientes</h1>
        <p className="text-texto-suave">Consulta los datos y pedidos de un cliente para resolver incidencias.</p>
      </header>

      {error && <Alerta tipo="error" titulo={error} />}

      <Tarjeta>
        <form onSubmit={buscar} role="search" className="flex flex-col gap-3 md:flex-row md:items-end">
          <CampoTexto
            etiqueta="Buscar cliente"
            name="buscar"
            value={texto}
            onChange={(evento) => setTexto(evento.target.value)}
            placeholder="Nombre, correo o teléfono"
            className="md:flex-1"
          />
          <div className="flex gap-2">
            <Boton tipo="submit">Buscar</Boton>
            <Boton variante="secundario" onClick={limpiar}>
              Limpiar
            </Boton>
          </div>
        </form>
      </Tarjeta>

      <Tarjeta titulo={cargando ? 'Resultados' : `Resultados (${clientes.length})`}>
        {cargando ? (
          <p className="text-texto-suave">Cargando clientes…</p>
        ) : clientes.length === 0 ? (
          <p className="text-texto-suave">No hay clientes que coincidan con la búsqueda.</p>
        ) : (
          <ul className="flex flex-col gap-2">
            {clientes.map((cliente) => (
              <li
                key={cliente.id}
                className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-borde bg-fondo px-3 py-2"
              >
                <div className="min-w-0">
                  <p className="font-medium">{cliente.nombre}</p>
                  <p className="truncate text-sm text-texto-suave">
                    {cliente.email} · {cliente.celular}
                  </p>
                  <p className="text-sm text-texto-suave">
                    Registrado el {fechaCorta(cliente.fecha_registro)} · {cliente.total_pedidos}{' '}
                    {cliente.total_pedidos === 1 ? 'pedido' : 'pedidos'}
                  </p>
                </div>
                <div className="flex items-center gap-3">
                  <span
                    className={`rounded-full border px-2 py-0.5 text-xs font-medium ${
                      cliente.activa ? 'border-exito text-exito' : 'border-aviso text-aviso'
                    }`}
                  >
                    {cliente.activa ? 'Activa' : 'Desactivada'}
                  </span>
                  <Boton
                    variante="secundario"
                    onClick={() => setSeleccionado(cliente)}
                    aria-label={`Ver ficha de ${cliente.nombre}`}
                  >
                    Ver ficha
                  </Boton>
                </div>
              </li>
            ))}
          </ul>
        )}
      </Tarjeta>

      {seleccionado && (
        <Modal
          titulo={seleccionado.nombre}
          alCerrar={cerrarFicha}
          ancho="max-w-2xl"
          acciones={
            <Boton variante="secundario" onClick={cerrarFicha}>
              Cerrar
            </Boton>
          }
        >
          <FichaCliente id={seleccionado.id} />
        </Modal>
      )}
    </div>
  )
}
