import { useCallback, useEffect, useState } from 'react'
import api from '../../api/cliente.js'
import { interpretarError } from '../../api/errores.js'
import { listarHistorialPedidos } from '../../api/pedidos.js'
import FichaPedido from '../../components/admin/FichaPedido.jsx'
import Alerta from '../../components/ui/Alerta.jsx'
import Boton from '../../components/ui/Boton.jsx'
import CampoTexto from '../../components/ui/CampoTexto.jsx'
import Modal from '../../components/ui/Modal.jsx'
import Selector from '../../components/ui/Selector.jsx'
import Tarjeta from '../../components/ui/Tarjeta.jsx'
import { datosEstado } from '../../utils/estadosPedido.js'
import { formatearPrecio } from '../../utils/formato.js'
import { textoRango, totalPaginas } from '../../utils/historial.js'
import { fechaHora } from '../../utils/tiempo.js'

const ESTADOS_OPCIONES = [
  { valor: 'pendiente_aprobacion', etiqueta: 'Pendiente de aprobación' },
  { valor: 'recibido', etiqueta: 'Recibido' },
  { valor: 'en_preparacion', etiqueta: 'En preparación' },
  { valor: 'listo_despacho', etiqueta: 'Listo para despacho' },
  { valor: 'recogido', etiqueta: 'Recogido' },
  { valor: 'en_camino', etiqueta: 'En camino' },
  { valor: 'entregado', etiqueta: 'Entregado' },
  { valor: 'cancelado', etiqueta: 'Cancelado' },
]

const FILTROS_INICIALES = {
  q: '',
  fechaInicio: '',
  fechaFin: '',
  sede: '',
  estado: '',
  repartidor: '',
  zona: '',
}

export default function HistorialPedidos() {
  const [pagina, setPagina] = useState(1)
  const [datos, setDatos] = useState({ count: 0, results: [] })
  const [cargando, setCargando] = useState(true)
  const [error, setError] = useState(null)
  const [seleccionado, setSeleccionado] = useState(null)

  // Estado de los filtros (borrador en formulario y aplicados en consulta)
  const [filtrosForm, setFiltrosForm] = useState(FILTROS_INICIALES)
  const [filtrosActivos, setFiltrosActivos] = useState(FILTROS_INICIALES)

  // Catálogos para los selectores
  const [sedes, setSedes] = useState([])
  const [repartidores, setRepartidores] = useState([])
  const [zonas, setZonas] = useState([])

  // Cargar catálogos (sedes, repartidores, zonas de cobertura) una sola vez
  useEffect(() => {
    let vigente = true
    Promise.all([
      api.get('/sedes/').catch(() => ({ data: [] })),
      api.get('/usuarios/repartidores/').catch(() => ({ data: [] })),
      api.get('/sedes/zonas-cobertura/').catch(() => ({ data: [] })),
    ]).then(([resSedes, resRepartidores, resZonas]) => {
      if (!vigente) return
      const listaSedes = Array.isArray(resSedes.data) ? resSedes.data : resSedes.data.results ?? []
      const listaRep = Array.isArray(resRepartidores.data)
        ? resRepartidores.data
        : resRepartidores.data.results ?? []
      const listaZonas = Array.isArray(resZonas.data) ? resZonas.data : resZonas.data.results ?? []

      setSedes(listaSedes)
      setRepartidores(listaRep)
      setZonas(listaZonas)
    })
    return () => {
      vigente = false
    }
  }, [])

  // Consultar historial con página + filtros activos
  useEffect(() => {
    let vigente = true
    setCargando(true)
    listarHistorialPedidos(pagina, filtrosActivos)
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
  }, [pagina, filtrosActivos])

  const cerrarFicha = useCallback(() => setSeleccionado(null), [])
  const paginas = totalPaginas(datos.count)

  // Zonas filtradas por la sede elegida en el formulario (si seleccionó una)
  const zonasDisponibles = filtrosForm.sede
    ? zonas.filter((z) => String(z.sede) === String(filtrosForm.sede))
    : zonas

  const hayFiltrosActivos = Object.values(filtrosActivos).some((val) => val !== '')

  function actualizarCampo(campo, valor) {
    setFiltrosForm((prev) => {
      const siguiente = { ...prev, [campo]: valor }
      // Si cambia la sede y la zona elegida no pertenece a la nueva sede, reiniciar zona
      if (campo === 'sede' && prev.zona) {
        const zonaSigueValida = zonas.some(
          (z) => String(z.id) === String(prev.zona) && (!valor || String(z.sede) === String(valor))
        )
        if (!zonaSigueValida) siguiente.zona = ''
      }
      return siguiente
    })
  }

  function aplicarFiltros(e) {
    e.preventDefault()
    setPagina(1)
    setFiltrosActivos({ ...filtrosForm })
  }

  function limpiarFiltros() {
    setFiltrosForm(FILTROS_INICIALES)
    setFiltrosActivos(FILTROS_INICIALES)
    setPagina(1)
  }

  function irA(nueva) {
    setPagina(nueva)
  }

  // Formatear nombre de repartidor según estructura devuelta por /usuarios/repartidores/
  const opcionesRepartidores = repartidores.map((r) => {
    const nombreCompleto =
      r.nombre ||
      (r.empleado ? `${r.empleado.nombres} ${r.empleado.apellidos}` : null) ||
      (r.nombres ? `${r.nombres} ${r.apellidos || ''}`.trim() : `Repartidor #${r.id}`)
    return { valor: r.id, etiqueta: nombreCompleto }
  })

  const opcionesZonas = zonasDisponibles.map((z) => ({
    valor: z.id,
    etiqueta: filtrosForm.sede ? z.nombre : `${z.nombre}${z.sede_nombre ? ` (${z.sede_nombre})` : ''}`,
  }))

  return (
    <div className="flex flex-col gap-6">
      <header>
        <h1 className="text-2xl font-bold">Historial y búsqueda de pedidos</h1>
        <p className="text-texto-suave">
          Audita pedidos de todas las sedes combinando fecha, sede, estado, repartidor y zona de envío.
        </p>
      </header>

      {/* Barra de filtros avanzada (HU-68) */}
      <Tarjeta titulo="Filtros de búsqueda">
        <form onSubmit={aplicarFiltros} className="flex flex-col gap-4">
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <CampoTexto
              etiqueta="Número de pedido"
              placeholder="Ej. PED-0042"
              value={filtrosForm.q}
              onChange={(e) => actualizarCampo('q', e.target.value)}
            />
            <CampoTexto
              tipo="date"
              etiqueta="Desde"
              value={filtrosForm.fechaInicio}
              onChange={(e) => actualizarCampo('fechaInicio', e.target.value)}
            />
            <CampoTexto
              tipo="date"
              etiqueta="Hasta"
              value={filtrosForm.fechaFin}
              onChange={(e) => actualizarCampo('fechaFin', e.target.value)}
            />
            <Selector
              etiqueta="Sede"
              textoVacio="Todas las sedes"
              opciones={sedes.map((s) => ({ valor: s.id, etiqueta: s.nombre }))}
              value={filtrosForm.sede}
              onChange={(e) => actualizarCampo('sede', e.target.value)}
            />
          </div>

          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            <Selector
              etiqueta="Estado"
              textoVacio="Todos los estados"
              opciones={ESTADOS_OPCIONES}
              value={filtrosForm.estado}
              onChange={(e) => actualizarCampo('estado', e.target.value)}
            />
            <Selector
              etiqueta="Repartidor"
              textoVacio="Todos los repartidores"
              opciones={opcionesRepartidores}
              value={filtrosForm.repartidor}
              onChange={(e) => actualizarCampo('repartidor', e.target.value)}
            />
            <Selector
              etiqueta="Zona de envío"
              textoVacio="Todas las zonas"
              opciones={opcionesZonas}
              value={filtrosForm.zona}
              onChange={(e) => actualizarCampo('zona', e.target.value)}
            />
          </div>

          <div className="flex flex-wrap items-center justify-between gap-3 border-t border-borde pt-3">
            <p className="text-sm text-texto-suave" aria-live="polite">
              {cargando ? (
                'Buscando coincidencias…'
              ) : (
                <>
                  <strong className="font-semibold text-texto">{datos.count}</strong>{' '}
                  {datos.count === 1 ? 'coincidencia encontrada' : 'coincidencias encontradas'}
                  {hayFiltrosActivos && ' con los filtros aplicados'}
                </>
              )}
            </p>

            <div className="flex flex-wrap items-center gap-2">
              <Boton
                type="button"
                variante="secundario"
                onClick={limpiarFiltros}
                disabled={cargando && !hayFiltrosActivos}
              >
                Limpiar filtros
              </Boton>
              <Boton type="submit" disabled={cargando}>
                Buscar pedidos
              </Boton>
            </div>
          </div>
        </form>
      </Tarjeta>

      {error && <Alerta tipo="error" titulo={error} />}

      <Tarjeta titulo={cargando || error ? 'Pedidos' : textoRango(pagina, datos.count)}>
        {cargando ? (
          <p className="text-texto-suave">Cargando pedidos…</p>
        ) : error ? (
          <p className="text-texto-suave">No se pudo cargar el historial.</p>
        ) : datos.results.length === 0 ? (
          <div className="flex flex-col items-start gap-3 py-2">
            <p className="text-texto-suave">
              {hayFiltrosActivos
                ? 'No se encontraron pedidos que coincidan con los filtros seleccionados.'
                : 'Todavía no hay pedidos registrados.'}
            </p>
            {hayFiltrosActivos && (
              <Boton variante="secundario" onClick={limpiarFiltros}>
                Limpiar filtros
              </Boton>
            )}
          </div>
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
                      <td className="py-2 pr-3">
                        {pedido.cliente ?? <span className="text-texto-suave">Sin cliente</span>}
                      </td>
                      <td className="py-2 pr-3">
                        <span
                          className={`rounded-full border px-2 py-0.5 text-xs font-medium whitespace-nowrap ${estado.clases}`}
                        >
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