import { useCallback, useEffect, useState } from 'react'
import { interpretarError } from '../../api/errores.js'
import { listarHistorialPedidos } from '../../api/pedidos.js'
import FichaPedido from '../../components/admin/FichaPedido.jsx'
import Alerta from '../../components/ui/Alerta.jsx'
import Boton from '../../components/ui/Boton.jsx'
import Modal from '../../components/ui/Modal.jsx'
import Tarjeta from '../../components/ui/Tarjeta.jsx'
import { datosEstado } from '../../utils/estadosPedido.js'
import { formatearPrecio } from '../../utils/formato.js'
import { textoRango, totalPaginas } from '../../utils/historial.js'
import { fechaHora } from '../../utils/tiempo.js'

// HU-66 · Historial completo de pedidos de todas las sedes (administrador).
// Del más reciente al más antiguo, de a 20 por página; "Ver ficha" abre las
// marcas de tiempo de cada cambio de estado.
export default function HistorialPedidos() {
  const [pagina, setPagina] = useState(1)
  const [datos, setDatos] = useState({ count: 0, results: [] })
  const [cargando, setCargando] = useState(true)
  const [error, setError] = useState(null)
  const [seleccionado, setSeleccionado] = useState(null)

  useEffect(() => {
    let vigente = true
    listarHistorialPedidos(pagina)
      .then((respuesta) => {
        if (!vigente) return
        setDatos(respuesta)
        setError(null)
      })
      .catch((fallo) => vigente && setError(interpretarError(fallo).general))
      .finally(() => vigente && setCargando(false))
    return () => {
      vigente = false
    }
  }, [pagina])

  const cerrarFicha = useCallback(() => setSeleccionado(null), [])
  const paginas = totalPaginas(datos.count)

  function irA(nueva) {
    setCargando(true)
    setPagina(nueva)
  }

  return (
    <div className="flex flex-col gap-6">
      <header>
        <h1 className="text-2xl font-bold">Historial de pedidos</h1>
        <p className="text-texto-suave">Todos los pedidos de todas las sedes, del más reciente al más antiguo.</p>
      </header>

      {error && <Alerta tipo="error" titulo={error} />}

      <Tarjeta titulo={cargando || error ? 'Pedidos' : textoRango(pagina, datos.count)}>
        {cargando ? (
          <p className="text-texto-suave">Cargando pedidos…</p>
        ) : error ? (
          <p className="text-texto-suave">No se pudo cargar el historial.</p>
        ) : datos.results.length === 0 ? (
          <p className="text-texto-suave">Todavía no hay pedidos registrados.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[44rem] text-left text-sm">
              <thead className="text-texto-suave">
                <tr className="border-b border-borde">
                  <th scope="col" className="py-2 pr-3 font-medium">Número</th>
                  <th scope="col" className="py-2 pr-3 font-medium">Fecha</th>
                  <th scope="col" className="py-2 pr-3 font-medium">Sede</th>
                  <th scope="col" className="py-2 pr-3 font-medium">Cliente</th>
                  <th scope="col" className="py-2 pr-3 font-medium">Estado</th>
                  <th scope="col" className="py-2 pr-3 text-right font-medium">Total</th>
                  <th scope="col" className="py-2"><span className="sr-only">Acciones</span></th>
                </tr>
              </thead>
              <tbody>
                {datos.results.map((pedido) => {
                  const estado = datosEstado(pedido.estado)
                  return (
                    <tr key={pedido.id} className="border-b border-borde last:border-0">
                      <td className="py-2 pr-3 font-medium">{pedido.numero_pedido}</td>
                      <td className="py-2 pr-3 whitespace-nowrap">{fechaHora(pedido.fecha_creacion)}</td>
                      <td className="py-2 pr-3">{pedido.sede.nombre}</td>
                      <td className="py-2 pr-3">{pedido.cliente ?? <span className="text-texto-suave">Sin cliente</span>}</td>
                      <td className="py-2 pr-3">
                        <span className={`rounded-full border px-2 py-0.5 text-xs font-medium whitespace-nowrap ${estado.clases}`}>
                          {estado.etiqueta}
                        </span>
                      </td>
                      <td className="py-2 pr-3 text-right whitespace-nowrap">
                        {pedido.total != null ? formatearPrecio(pedido.total) : '—'}
                      </td>
                      <td className="py-2 text-right">
                        <Boton
                          variante="secundario"
                          onClick={() => setSeleccionado(pedido)}
                          aria-label={`Ver ficha del pedido ${pedido.numero_pedido}`}
                        >
                          Ver ficha
                        </Boton>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}

        {paginas > 1 && (
          <nav aria-label="Páginas del historial" className="mt-4 flex items-center justify-between gap-3">
            <Boton variante="secundario" disabled={pagina === 1 || cargando} onClick={() => irA(pagina - 1)}>
              ← Anterior
            </Boton>
            <p className="text-sm text-texto-suave">
              Página {pagina} de {paginas}
            </p>
            <Boton variante="secundario" disabled={pagina === paginas || cargando} onClick={() => irA(pagina + 1)}>
              Siguiente →
            </Boton>
          </nav>
        )}
      </Tarjeta>

      {seleccionado && (
        <Modal
          titulo={`Pedido ${seleccionado.numero_pedido}`}
          alCerrar={cerrarFicha}
          ancho="max-w-2xl"
          acciones={
            <Boton variante="secundario" onClick={cerrarFicha}>
              Cerrar
            </Boton>
          }
        >
          <FichaPedido id={seleccionado.id} />
        </Modal>
      )}
    </div>
  )
}
