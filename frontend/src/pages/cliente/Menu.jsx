import { useEffect, useState } from 'react'
import { listarSedesMenu, obtenerMenuSede, validarCarrito } from '../../api/menu.js'
import { interpretarError } from '../../api/errores.js'
import { useCarrito } from '../../carrito/useCarrito.js'
import PersonalizarProducto from '../../components/carrito/PersonalizarProducto.jsx'
import TarjetaProducto from '../../components/menu/TarjetaProducto.jsx'
import Alerta from '../../components/ui/Alerta.jsx'
import Boton from '../../components/ui/Boton.jsx'
import CampoTexto from '../../components/ui/CampoTexto.jsx'
import Selector from '../../components/ui/Selector.jsx'
import { formatearPrecio } from '../../utils/formato.js'

const CLAVE_SEDE = 'domipedidosx.sede'
const TODAS = 'todas'
const CATEGORIA_COMBOS = 'combos'

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

// HU-18 & HU-19 · Consultar el menú por categorías y buscar productos por nombre.
export default function Menu() {
  const [sedes, setSedes] = useState([])
  const [sedesCargadas, setSedesCargadas] = useState(false)
  const [sedeId, setSedeId] = useState(leerSedeGuardada)
  const [resultado, setResultado] = useState(null)
  const [categoriaId, setCategoriaId] = useState(TODAS)
  const [busqueda, setBusqueda] = useState('')
  const [busquedaDebounced, setBusquedaDebounced] = useState('')
  const [error, setError] = useState(null)
  const [aviso, setAviso] = useState(null)
  const [recargaMenu, setRecargaMenu] = useState(0)
  const [personalizando, setPersonalizando] = useState(null)
  const carrito = useCarrito()

  // Debounce de 300ms para evitar peticiones por cada tecla (HU-19)
  useEffect(() => {
    const timer = setTimeout(() => {
      setBusquedaDebounced(busqueda.trim())
    }, 300)
    return () => clearTimeout(timer)
  }, [busqueda])

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

  // Menú de la sede elegida + búsqueda debounced.
  useEffect(() => {
    if (!sedesCargadas || !sedeId) return undefined
    let vigente = true
    obtenerMenuSede(sedeId, { q: busquedaDebounced })
      .then((menu) => {
        if (vigente) setResultado({ sedeId, q: busquedaDebounced, menu })
      })
      .catch((err) => {
        if (vigente) setResultado({ sedeId, q: busquedaDebounced, error: interpretarError(err).general })
      })
    return () => {
      vigente = false
    }
  }, [sedeId, sedesCargadas, recargaMenu, busquedaDebounced])

  function cambiarSede(evento) {
    const nueva = evento.target.value
    const otraSede = carrito.lineas.length > 0 && String(carrito.sedeId) !== nueva
    if (otraSede) {
      const confirmado = window.confirm(
        'Tu carrito tiene productos de otra sede. Si cambias de sede se vaciará. ¿Quieres continuar?',
      )
      if (!confirmado) return
      carrito.vaciar()
    }
    setSedeId(nueva)
    setCategoriaId(TODAS)
    setBusqueda('')
    setBusquedaDebounced('')
    setAviso(null)
    if (nueva) guardarSede(nueva)
  }

  function limpiarBusqueda() {
    setBusqueda('')
    setBusquedaDebounced('')
  }

  async function agregar(producto) {
    setAviso(null)
    try {
      const { valido } = await validarCarrito(sedeId, [producto.id])
      if (!valido) {
        setAviso({
          tipo: 'aviso',
          texto: `${producto.nombre} acaba de quedar no disponible en esta sede y no se puede agregar.`,
        })
        setRecargaMenu((valor) => valor + 1)
        return
      }
      setPersonalizando(producto)
    } catch (err) {
      setAviso({ tipo: 'error', texto: interpretarError(err).general })
    }
  }

  function agregarCombo(combo) {
    setAviso(null)
    if (!combo.disponible) {
      setAviso({
        tipo: 'aviso',
        texto: combo.motivo_no_disponible || `${combo.nombre} no está disponible.`,
      })
      return
    }
    const yaEnCarrito = carrito.lineas.find((l) => l.combo?.id === combo.id)?.cantidad ?? 0
    if (combo.cupo_restante !== null && yaEnCarrito + 1 > combo.cupo_restante) {
      setAviso({
        tipo: 'aviso',
        texto: `Solo quedan ${combo.cupo_restante} unidades disponibles hoy de ${combo.nombre}.`,
      })
      return
    }
    carrito.agregar(Number(sedeId), {
      combo: {
        id: combo.id,
        nombre: combo.nombre,
        descripcion: combo.descripcion,
        productos_incluidos: combo.productos_incluidos,
      },
      cantidad: 1,
      precio_unitario: combo.precio,
    })
    setAviso({
      tipo: 'exito',
      texto: `Agregaste 1 × ${combo.nombre} a tu carrito.`,
    })
  }

  const opcionesSede = sedes.map((sede) => ({
    valor: String(sede.id),
    etiqueta: `${sede.nombre} · ${sede.barrio}`,
  }))

  const actual =
    resultado?.sedeId === sedeId && resultado?.q === busquedaDebounced ? resultado : null
  const cargandoMenu = Boolean(sedeId) && sedesCargadas && !actual
  const categorias = actual?.menu?.categorias ?? []
  const combos = actual?.menu?.combos ?? []
  const hayBusqueda = busquedaDebounced.length > 0

  const mostrarCombos =
    combos.length > 0 && (categoriaId === TODAS || categoriaId === CATEGORIA_COMBOS)

  const filtradas =
    categoriaId === CATEGORIA_COMBOS
      ? []
      : categoriaId === TODAS
        ? categorias.filter((categoria) => categoria.productos.length > 0)
        : categorias.filter((categoria) => String(categoria.id) === categoriaId)

  const opcionesFiltro = [
    { id: TODAS, nombre: 'Todas' },
    ...(combos.length > 0 ? [{ id: CATEGORIA_COMBOS, nombre: `Combos (${combos.length})` }] : []),
    ...categorias,
  ]

  return (
    <div className="flex flex-col gap-6">
      <header className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold">
            Menú{actual?.menu ? ` · ${actual.menu.sede.nombre}` : ''}
          </h1>
          <p className="text-texto-suave">Elige la sede, busca tu plato o explora por categoría.</p>
        </div>

        <div className="flex flex-col gap-3 sm:flex-row sm:items-end">
          {sedeId && (
            <div className="flex items-end gap-2">
              <CampoTexto
                etiqueta="Buscar producto"
                placeholder="Ej. Hamburguesa, limonada…"
                value={busqueda}
                onChange={(e) => setBusqueda(e.target.value)}
                aria-label="Buscar productos por nombre"
                className="sm:w-64"
              />
              {busqueda && (
                <Boton
                  type="button"
                  variante="secundario"
                  onClick={limpiarBusqueda}
                  aria-label="Limpiar búsqueda"
                >
                  Limpiar
                </Boton>
              )}
            </div>
          )}

          <Selector
            etiqueta="Sede"
            opciones={opcionesSede}
            value={sedeId}
            onChange={cambiarSede}
            textoVacio={sedesCargadas ? 'Selecciona una sede' : 'Cargando sedes…'}
            disabled={!sedesCargadas}
            className="sm:w-64"
          />
        </div>
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

          {filtradas.length === 0 && !mostrarCombos && (
            <div className="flex flex-col items-start gap-3">
              <Alerta tipo="info">
                {hayBusqueda
                  ? `No encontramos productos que coincidan con "${busquedaDebounced}"${
                      categoriaId !== TODAS ? ' en esta categoría' : ''
                    }.`
                  : 'El menú de esta sede todavía no tiene productos.'}
              </Alerta>
              {hayBusqueda && (
                <Boton variante="secundario" onClick={limpiarBusqueda}>
                  Mostrar todo el menú
                </Boton>
              )}
            </div>
          )}

          {mostrarCombos && (
            <section aria-labelledby="categoria-combos">
              <div className="mb-3 flex flex-wrap items-baseline justify-between gap-2">
                <h2 id="categoria-combos" className="text-xl font-bold">
                  Combos y promociones
                </h2>
                <span className="text-xs text-texto-suave">Precio especial por paquete</span>
              </div>
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
                {combos.map((combo) => (
                  <article
                    key={combo.id}
                    className="flex flex-col justify-between gap-3 rounded-xl border border-borde bg-superficie p-4"
                  >
                    <div className="space-y-2">
                      <div className="flex items-start justify-between gap-2">
                        <h3 className="text-lg font-bold">{combo.nombre}</h3>
                        {Number(combo.ahorro) > 0 && (
                          <span className="rounded-full bg-exito/15 px-2.5 py-0.5 text-xs font-semibold text-exito">
                            Ahorras {formatearPrecio(combo.ahorro)}
                          </span>
                        )}
                      </div>

                      {combo.descripcion && (
                        <p className="text-sm text-texto-suave">{combo.descripcion}</p>
                      )}

                      {combo.productos_incluidos?.length > 0 && (
                        <ul className="space-y-0.5 rounded-lg bg-fondo px-3 py-2 text-xs text-texto-suave">
                          {combo.productos_incluidos.map((item) => (
                            <li key={item.producto_id}>
                              • {item.cantidad}× {item.nombre}
                            </li>
                          ))}
                        </ul>
                      )}

                      {combo.condicion && (
                        <p className="text-xs text-texto-suave">Condición: {combo.condicion}</p>
                      )}

                      {combo.cupo_restante !== null && combo.disponible && (
                        <p className="text-xs font-medium text-aviso">
                          Quedan {combo.cupo_restante} disponibles hoy
                        </p>
                      )}
                    </div>

                    <div className="flex items-center justify-between gap-3 border-t border-borde pt-3">
                      <div>
                        {Number(combo.suma_individual) > Number(combo.precio) && (
                          <p className="text-xs text-texto-suave line-through">
                            {formatearPrecio(combo.suma_individual)}
                          </p>
                        )}
                        <p className="text-lg font-bold text-marca">
                          {formatearPrecio(combo.precio)}
                        </p>
                      </div>

                      <Boton
                        type="button"
                        variante="primario"
                        disabled={!combo.disponible}
                        onClick={() => agregarCombo(combo)}
                      >
                        {combo.disponible ? 'Agregar combo' : 'No disponible'}
                      </Boton>
                    </div>

                    {!combo.disponible && combo.motivo_no_disponible && (
                      <p className="text-xs text-error">{combo.motivo_no_disponible}</p>
                    )}
                  </article>
                ))}
              </div>
            </section>
          )}

          {filtradas.map((categoria) => (
            <section key={categoria.id} aria-labelledby={`categoria-${categoria.id}`}>
              <h2 id={`categoria-${categoria.id}`} className="mb-3 text-xl font-bold">
                {categoria.nombre}
              </h2>
              {categoria.productos.length === 0 ? (
                <Alerta tipo="info">
                  {hayBusqueda
                    ? `No hay coincidencias para "${busquedaDebounced}" en ${categoria.nombre}.`
                    : 'Esta categoría todavía no tiene productos.'}
                </Alerta>
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

      {personalizando && (
        <PersonalizarProducto
          sedeId={Number(sedeId)}
          producto={personalizando}
          alCerrar={() => setPersonalizando(null)}
          alAgregar={(linea) =>
            setAviso({
              tipo: 'exito',
              texto: `Agregaste ${linea.cantidad} × ${linea.producto.nombre} a tu carrito.`,
            })
          }
        />
      )}
    </div>
  )
}