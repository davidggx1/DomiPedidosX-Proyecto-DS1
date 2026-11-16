import { useEffect, useState } from 'react'
import { actualizarCombo, desactivarCombo, listarCombos } from '../../api/combos.js'
import { interpretarError } from '../../api/errores.js'
import { listarProductos } from '../../api/menu.js'
import FormularioCombo from '../../components/combos/FormularioCombo.jsx'
import Alerta from '../../components/ui/Alerta.jsx'
import Boton from '../../components/ui/Boton.jsx'
import Tarjeta from '../../components/ui/Tarjeta.jsx'
import { formatearPrecio } from '../../utils/formato.js'
import {
  ETIQUETA_ESTADO_COMBO,
  FILTROS_COMBO,
  claseEstadoCombo,
  contarPorEstadoCombo,
  estadoCombo,
  filtrarCombos,
  productosElegibles,
} from '../../utils/combos.js'
import { cupoAgotado, formatearFecha, textoCupo } from '../../utils/promociones.js'

// HU-85 · Combos de la sede: crear, editar y desactivar (operador y administrador).
export default function Combos() {
  const [combos, setCombos] = useState(null) // null mientras carga
  const [productos, setProductos] = useState([])
  const [errorCarga, setErrorCarga] = useState(null)
  const [filtro, setFiltro] = useState('todos')
  const [editando, setEditando] = useState(null)
  const [mensaje, setMensaje] = useState(null)
  const [recarga, setRecarga] = useState(0)

  useEffect(() => {
    let vigente = true
    listarProductos()
      .then((datos) => {
        if (vigente) setProductos(productosElegibles(datos))
      })
      .catch(() => {})
    return () => {
      vigente = false
    }
  }, [])

  useEffect(() => {
    let vigente = true
    listarCombos()
      .then((datos) => {
        if (!vigente) return
        setCombos(datos)
        setErrorCarga(null)
      })
      .catch((error) => {
        if (vigente) setErrorCarga(interpretarError(error).general)
      })
    return () => {
      vigente = false
    }
  }, [recarga])

  function recargar() {
    setRecarga((valor) => valor + 1)
  }

  function alGuardar(combo, fueEdicion) {
    setMensaje({
      tipo: 'exito',
      texto: fueEdicion
        ? `Se guardaron los cambios de "${combo.nombre}". Aplican a las compras que se hagan desde ahora.`
        : `Se creó el combo "${combo.nombre}".`,
    })
    setEditando(null)
    recargar()
  }

  async function desactivar(combo) {
    const confirmado = window.confirm(
      `¿Desactivar el combo "${combo.nombre}"? Dejará de ofrecerse, pero se conserva su historial.`,
    )
    if (!confirmado) return
    try {
      await desactivarCombo(combo.id)
      if (editando?.id === combo.id) setEditando(null)
      setMensaje({ tipo: 'exito', texto: `Se desactivó el combo "${combo.nombre}".` })
      recargar()
    } catch (error) {
      setMensaje({ tipo: 'error', texto: interpretarError(error).general })
    }
  }

  async function reactivar(combo) {
    try {
      await actualizarCombo(combo.id, { activo: true })
      setMensaje({ tipo: 'exito', texto: `Se reactivó el combo "${combo.nombre}".` })
      recargar()
    } catch (error) {
      setMensaje({ tipo: 'error', texto: interpretarError(error).general })
    }
  }

  const lista = combos ?? []
  const conteo = contarPorEstadoCombo(lista)
  const visibles = filtrarCombos(lista, filtro)

  return (
    <div className="flex flex-col gap-6">
      <header>
        <h1 className="text-2xl font-bold">Combos</h1>
        <p className="text-texto-suave">
          Paquetes de productos a un precio especial. Si un producto se agota o se desactiva, el combo
          pasa solo a "No disponible".
        </p>
      </header>

      {mensaje && <Alerta tipo={mensaje.tipo} titulo={mensaje.texto} />}
      {errorCarga && <Alerta tipo="error" titulo={errorCarga} />}

      <div className="grid gap-6 lg:grid-cols-[minmax(0,2fr)_minmax(0,3fr)]">
        <Tarjeta>
          <FormularioCombo
            key={editando?.id ?? 'nuevo'}
            combo={editando}
            productos={productos}
            alGuardar={alGuardar}
            alCancelar={() => setEditando(null)}
          />
        </Tarjeta>

        <Tarjeta titulo="Combos">
          <div className="mb-4 flex flex-wrap gap-2" role="group" aria-label="Filtrar por estado">
            {FILTROS_COMBO.map(({ valor, etiqueta }) => (
              <Boton
                key={valor}
                variante={filtro === valor ? 'primario' : 'secundario'}
                aria-pressed={filtro === valor}
                onClick={() => setFiltro(valor)}
              >
                {etiqueta} ({conteo[valor]})
              </Boton>
            ))}
          </div>

          {combos === null && !errorCarga ? (
            <p className="text-texto-suave">Cargando combos…</p>
          ) : visibles.length === 0 ? (
            <p className="text-texto-suave">
              {lista.length === 0 ? 'Todavía no hay combos registrados.' : 'No hay combos en este estado.'}
            </p>
          ) : (
            <ul className="flex flex-col gap-2">
              {visibles.map((combo) => {
                const estado = estadoCombo(combo)
                return (
                  <li
                    key={combo.id}
                    className="flex flex-wrap items-start justify-between gap-3 rounded-lg border border-borde bg-fondo px-3 py-2"
                  >
                    <div className="min-w-0 flex-1">
                      <p className="font-medium">
                        {combo.nombre}{' '}
                        <span className="text-texto-suave">· {formatearPrecio(combo.precio)}</span>
                      </p>
                      <p className="text-sm text-texto-suave">
                        {combo.productos_detalle
                          .map((linea) => `${linea.cantidad} × ${linea.nombre}`)
                          .join(' + ')}
                      </p>
                      <p className="text-sm text-texto-suave">
                        Total individual: {formatearPrecio(combo.suma_individual)} · Ahorro:{' '}
                        {formatearPrecio(combo.ahorro)}
                      </p>
                      <p className="text-sm text-texto-suave">
                        {formatearFecha(combo.fecha_inicio)} – {formatearFecha(combo.fecha_vencimiento)}
                        {combo.sede_nombre ? ` · ${combo.sede_nombre}` : ''}
                      </p>
                      {textoCupo(combo) && (
                        <p className={`text-sm ${cupoAgotado(combo) ? 'text-aviso' : 'text-texto-suave'}`}>
                          {textoCupo(combo)}
                        </p>
                      )}
                      <span
                        className={`mt-1 inline-block rounded-full border px-2 py-0.5 text-xs font-medium ${claseEstadoCombo(
                          estado,
                        )}`}
                      >
                        {ETIQUETA_ESTADO_COMBO[estado]}
                      </span>
                      {estado === 'no_disponible' && combo.motivo_no_disponible && (
                        <p className="mt-1 text-sm text-aviso">{combo.motivo_no_disponible}</p>
                      )}
                    </div>
                    <div className="flex gap-2">
                      {combo.activo ? (
                        <>
                          <Boton
                            variante="secundario"
                            onClick={() => setEditando(combo)}
                            aria-label={`Editar ${combo.nombre}`}
                          >
                            Editar
                          </Boton>
                          <Boton
                            variante="peligro"
                            onClick={() => desactivar(combo)}
                            aria-label={`Desactivar ${combo.nombre}`}
                          >
                            Desactivar
                          </Boton>
                        </>
                      ) : (
                        <Boton
                          variante="secundario"
                          onClick={() => reactivar(combo)}
                          aria-label={`Reactivar ${combo.nombre}`}
                        >
                          Reactivar
                        </Boton>
                      )}
                    </div>
                  </li>
                )
              })}
            </ul>
          )}
        </Tarjeta>
      </div>
    </div>
  )
}