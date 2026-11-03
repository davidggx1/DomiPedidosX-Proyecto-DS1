import { useEffect, useState } from 'react'
import { listarSedesMenu, obtenerMenuSede, validarCarrito } from '../../api/menu.js'
import { interpretarError } from '../../api/errores.js'
import TarjetaProducto from '../../components/menu/TarjetaProducto.jsx'
import Alerta from '../../components/ui/Alerta.jsx'
import Boton from '../../components/ui/Boton.jsx'
import Selector from '../../components/ui/Selector.jsx'

const CLAVE_SEDE = 'domipedidosx.sede'
const TODAS = 'todas'

// La sede elegida se recuerda en este navegador para la próxima visita.
function leerSedeGuardada() {
  try {
    return localStorage.getItem(CLAVE_SEDE) ?? ''
  } catch {
    return ''
  }
}

function guardarSede(sedeId) {
  try {
    localStorage.setItem(CLAVE_SEDE, sedeId)
  } catch {
    // Sin almacenamiento disponible: se vuelve a elegir en la próxima visita.
  }
}

// HU-18 · Consultar el menú por categorías (vista del cliente).
// En el PMV el cliente elige la sede; la asignación por zona llega con HU-58.
export default function Menu() {
  const [sedes, setSedes] = useState([])
  const [sedesCargadas, setSedesCargadas] = useState(false)
  const [sedeId, setSedeId] = useState(leerSedeGuardada)
  const [resultado, setResultado] = useState(null)
  const [categoriaId, setCategoriaId] = useState(TODAS)
  const [error, setError] = useState(null)
  const [aviso, setAviso] = useState(null)
  const [recargaMenu, setRecargaMenu] = useState(0)

  // Sedes activas. Si la sede guardada ya no está activa, se descarta.
  useEffect(() => {
    let vigente = true
    listarSedesMenu()
      .then((lista) => {
        if (!vigente) return
        setSedes(lista)
        setSedeId((actual) => {
          if (lista.some((sede) => String(sede.id) === actual)) return actual
          return lista.length === 1 ? String(lista[0].id) : ''
        })
      })
      .catch((err) => {
        if (vigente) setError(interpretarError(err).general)
      })
      .finally(() => {
        if (vigente) setSedesCargadas(true)
      })
    return () => {
      vigente = false
    }
  }, [])

  // Menú de la sede elegida.
  useEffect(() => {
    if (!sedesCargadas || !sedeId) return undefined
    let vigente = true
    obtenerMenuSede(sedeId)
      .then((menu) => {
        if (vigente) setResultado({ sedeId, menu })
      })
      .catch((err) => {
        if (vigente) setResultado({ sedeId, error: interpretarError(err).general })
      })
    return () => {
      vigente = false
    }
  }, [sedeId, sedesCargadas, recargaMenu])

  function cambiarSede(evento) {
    const nueva = evento.target.value
    setSedeId(nueva)
    setCategoriaId(TODAS)
    setAviso(null)
    if (nueva) guardarSede(nueva)
  }

  // Hook del carrito (HU-13): antes de agregar se confirma que el producto siga
  // disponible en la sede. HU-23 repetirá esta validación al confirmar el pedido.
  async function agregar(producto) {
    setAviso(null)
    try {
      const { valido } = await validarCarrito(sedeId, [producto.id])
      if (!valido) {
        setAviso({
          tipo: 'aviso',
          texto: `"${producto.nombre}" acaba de quedar no disponible en esta sede y no se puede agregar.`,
        })
        setRecargaMenu((valor) => valor + 1)
        return
      }
      setAviso({
        tipo: 'info',
        texto: `Elegiste "${producto.nombre}". Muy pronto podrás agregarlo a tu carrito.`,
      })
    } catch (err) {
      setAviso({ tipo: 'error', texto: interpretarError(err).general })
    }
  }

  const opcionesSede = sedes.map((sede) => ({
    valor: String(sede.id),
    etiqueta: `${sede.nombre} · ${sede.barrio}`,
  }))

  const actual = resultado?.sedeId === sedeId ? resultado : null
  const cargandoMenu = Boolean(sedeId) && sedesCargadas && !actual
  const categorias = actual?.menu?.categorias ?? []
  const filtradas =
    categoriaId === TODAS
      ? categorias.filter((categoria) => categoria.productos.length > 0)
      : categorias.filter((categoria) => String(categoria.id) === categoriaId)
  const opcionesFiltro = [{ id: TODAS, nombre: 'Todas' }, ...categorias]

  return (
    <div className="flex flex-col gap-6">
      <header className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold">
            Menú{actual?.menu ? ` · ${actual.menu.sede.nombre}` : ''}
          </h1>
          <p className="text-texto-suave">Elige la sede y explora los productos por categoría.</p>
        </div>
        <Selector
          etiqueta="Sede"
          opciones={opcionesSede}
          value={sedeId}
          onChange={cambiarSede}
          textoVacio={sedesCargadas ? 'Selecciona una sede' : 'Cargando sedes…'}
          disabled={!sedesCargadas}
          className="sm:w-72"
        />
      </header>

      {error && <Alerta tipo="error" titulo={error} />}
      {actual?.error && <Alerta tipo="error" titulo={actual.error} />}
      {aviso && <Alerta tipo={aviso.tipo}>{aviso.texto}</Alerta>}

      {sedesCargadas && sedes.length === 0 && !error && (
        <Alerta tipo="aviso" titulo="Por ahora no hay sedes disponibles." />
      )}

      {sedesCargadas && sedes.length > 0 && !sedeId && (
        <p className="text-texto-suave">Selecciona una sede para ver su menú.</p>
      )}

      {cargandoMenu && <p className="text-texto-suave">Cargando menú…</p>}

      {actual?.menu && (
        <>
          <div role="group" aria-label="Filtrar por categoría" className="flex flex-wrap gap-2">
            {opcionesFiltro.map((categoria) => {
              const valor = String(categoria.id)
              const activa = categoriaId === valor
              return (
                <Boton
                  key={valor}
                  variante={activa ? 'primario' : 'secundario'}
                  aria-pressed={activa}
                  onClick={() => setCategoriaId(valor)}
                >
                  {categoria.nombre}
                </Boton>
              )
            })}
          </div>

          {filtradas.length === 0 && categoriaId === TODAS && (
            <Alerta tipo="info">El menú de esta sede todavía no tiene productos.</Alerta>
          )}

          {filtradas.map((categoria) => (
            <section key={categoria.id} aria-labelledby={`categoria-${categoria.id}`}>
              <h2 id={`categoria-${categoria.id}`} className="mb-3 text-xl font-bold">
                {categoria.nombre}
              </h2>
              {categoria.productos.length === 0 ? (
                <Alerta tipo="info">Esta categoría todavía no tiene productos.</Alerta>
              ) : (
                <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
                  {categoria.productos.map((producto) => (
                    <TarjetaProducto key={producto.id} producto={producto} alAgregar={agregar} />
                  ))}
                </div>
              )}
            </section>
          ))}
        </>
      )}
    </div>
  )
}
