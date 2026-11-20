import { useEffect, useState } from 'react'
import { useMensajeTemporal } from '../../components/ui/useMensajeTemporal.js'
import { interpretarError } from '../../api/errores.js'
import {
  actualizarPromocion,
  desactivarPromocion,
  listarPromociones,
} from '../../api/promociones.js'
import FormularioPromocion from '../../components/promociones/FormularioPromocion.jsx'
import Alerta from '../../components/ui/Alerta.jsx'
import Boton from '../../components/ui/Boton.jsx'
import Tarjeta from '../../components/ui/Tarjeta.jsx'
import { formatearPrecio } from '../../utils/formato.js'
import {
  ETIQUETA_ESTADO,
  FILTROS_ESTADO,
  claseEstado,
  cupoAgotado,
  contarPorEstado,
  filtrarPorEstado,
  textoCupo,
  textoPorcentaje,
  textoVigencia,
} from '../../utils/promociones.js'

function textoDescuento(promocion) {
  return promocion.tipo_descuento === 'porcentaje'
    ? textoPorcentaje(promocion.valor)
    : formatearPrecio(promocion.valor)
}

// HU-84 · Promociones de la sede (vista del operador): crear, editar y desactivar.
export default function Promociones() {
  const [promociones, setPromociones] = useState(null) // null mientras carga
  const [errorCarga, setErrorCarga] = useState(null)
  const [filtro, setFiltro] = useState('todas')
  const [editando, setEditando] = useState(null)
  const [mensaje, setMensaje] = useMensajeTemporal()
  const [recarga, setRecarga] = useState(0)

  useEffect(() => {
    let vigente = true
    listarPromociones()
      .then((datos) => {
        if (!vigente) return
        setPromociones(datos)
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

  function alGuardar(promocion, fueEdicion) {
    setMensaje({
      tipo: 'exito',
      texto: fueEdicion
        ? `Se guardaron los cambios de ${promocion.nombre}. Aplican a las compras que se hagan desde ahora.`
        : `Se creó la promoción ${promocion.nombre}.`,
    })
    setEditando(null)
    recargar()
  }

  async function desactivar(promocion) {
    const confirmado = window.confirm(
      `¿Desactivar la promoción ${promocion.nombre}? Dejará de poder usarse, pero se conserva su historial.`,
    )
    if (!confirmado) return
    try {
      await desactivarPromocion(promocion.id)
      if (editando?.id === promocion.id) setEditando(null)
      setMensaje({ tipo: 'exito', texto: `Se desactivó la promoción ${promocion.nombre}.` })
      recargar()
    } catch (error) {
      setMensaje({ tipo: 'error', texto: interpretarError(error).general })
    }
  }

  async function reactivar(promocion) {
    try {
      const actualizada = await actualizarPromocion(promocion.id, { activa: true })
      setMensaje(
        actualizada.estado === 'vencida'
          ? {
              tipo: 'aviso',
              texto: `Se reactivó ${promocion.nombre}, pero sigue vencida. Cambia su fecha de fin para poder usarla.`,
            }
          : { tipo: 'exito', texto: `Se reactivó la promoción ${promocion.nombre}.` },
      )
      recargar()
    } catch (error) {
      const { general, campos } = interpretarError(error)
      setMensaje({ tipo: 'error', texto: campos.nombre ?? general })
    }
  }

  const lista = promociones ?? []
  const conteo = contarPorEstado(lista)
  const visibles = filtrarPorEstado(lista, filtro)

  return (
    <div className="flex flex-col gap-6">
      <header>
        <h1 className="text-2xl font-bold">Promociones</h1>
        <p className="text-texto-suave">
          Descuentos de tu sede con vigencia y condiciones. Una promoción inactiva o vencida no se puede usar.
        </p>
      </header>

      {mensaje && <Alerta tipo={mensaje.tipo} titulo={mensaje.texto} />}
      {errorCarga && <Alerta tipo="error" titulo={errorCarga} />}

      <div className="grid gap-6 lg:grid-cols-[minmax(0,2fr)_minmax(0,3fr)]">
        <Tarjeta>
          <FormularioPromocion
            key={editando?.id ?? 'nueva'}
            promocion={editando}
            alGuardar={alGuardar}
            alCancelar={() => setEditando(null)}
          />
        </Tarjeta>

        <Tarjeta titulo="Promociones de la sede">
          <div className="mb-4 flex flex-wrap gap-2" role="group" aria-label="Filtrar por estado">
            {FILTROS_ESTADO.map(({ valor, etiqueta }) => (
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

          {promociones === null && !errorCarga ? (
            <p className="text-texto-suave">Cargando promociones…</p>
          ) : visibles.length === 0 ? (
            <p className="text-texto-suave">
              {lista.length === 0
                ? 'Todavía no hay promociones registradas.'
                : 'No hay promociones en este estado.'}
            </p>
          ) : (
            <ul className="flex flex-col gap-2">
              {visibles.map((promocion) => (
                <li
                  key={promocion.id}
                  className="flex flex-wrap items-start justify-between gap-3 rounded-lg border border-borde bg-fondo px-3 py-2"
                >
                  <div className="min-w-0 flex-1">
                    <p className="font-medium">
                      {promocion.nombre}{' '}
                      <span className="text-texto-suave">· {textoDescuento(promocion)} de descuento</span>
                    </p>
                    <p className="text-sm text-texto-suave">{textoVigencia(promocion)}</p>
                    {textoCupo(promocion) && (
                      <p
                        className={`text-sm ${cupoAgotado(promocion) ? 'text-aviso' : 'text-texto-suave'}`}
                      >
                        {textoCupo(promocion)}
                      </p>
                    )}
                    {promocion.condiciones && (
                      <p className="text-sm text-texto-suave">{promocion.condiciones}</p>
                    )}
                    <span
                      className={`mt-1 inline-block rounded-full border px-2 py-0.5 text-xs font-medium ${claseEstado(
                        promocion.estado,
                      )}`}
                    >
                      {ETIQUETA_ESTADO[promocion.estado] ?? promocion.estado}
                    </span>
                  </div>
                  <div className="flex gap-2">
                    {promocion.activa ? (
                      <>
                        <Boton
                          variante="secundario"
                          onClick={() => setEditando(promocion)}
                          aria-label={`Editar ${promocion.nombre}`}
                        >
                          Editar
                        </Boton>
                        <Boton
                          variante="peligro"
                          onClick={() => desactivar(promocion)}
                          aria-label={`Desactivar ${promocion.nombre}`}
                        >
                          Desactivar
                        </Boton>
                      </>
                    ) : (
                      <Boton
                        variante="secundario"
                        onClick={() => reactivar(promocion)}
                        aria-label={`Reactivar ${promocion.nombre}`}
                      >
                        Reactivar
                      </Boton>
                    )}
                  </div>
                </li>
              ))}
            </ul>
          )}
        </Tarjeta>
      </div>
    </div>
  )
}