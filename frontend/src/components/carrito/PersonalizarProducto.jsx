import { useEffect, useRef, useState } from 'react'
import { obtenerDetalleProducto, validarLineaCarrito } from '../../api/menu.js'
import { interpretarError } from '../../api/errores.js'
import { useCarrito } from '../../carrito/useCarrito.js'
import { bloqueosPorInsumo, buscarLineaIgual, lineaParaValidar, precioUnitario } from '../../utils/carrito.js'
import { formatearPrecio } from '../../utils/formato.js'
import Alerta from '../ui/Alerta.jsx'
import Boton from '../ui/Boton.jsx'
import Casilla from '../ui/Casilla.jsx'
import Contador from './Contador.jsx'

// Elección inicial: la de la línea que se edita o, si es nueva, el primer tamaño.
function eleccionInicial(detalle, linea) {
  const cantidades = Object.fromEntries(
    (linea?.adiciones ?? []).map((item) => [item.adicion, item.cantidad]),
  )
  return {
    tamanoId: linea?.tamano?.id ?? detalle.tamanos[0]?.id ?? null,
    adiciones: Object.fromEntries(
      detalle.adiciones.map((item) => [item.adicion, cantidades[item.adicion] ?? 0]),
    ),
    exclusiones: new Set((linea?.exclusiones ?? []).map((item) => item.id)),
    cantidad: linea?.cantidad ?? 1,
  }
}

// HU-21 · Diálogo para elegir tamaño, adiciones, ingredientes a quitar y cantidad.
// Con `linea` edita una línea del carrito; sin ella agrega una nueva.
export default function PersonalizarProducto({ sedeId, producto, linea = null, alCerrar, alAgregar }) {
  const dialogo = useRef(null)
  const { lineas, agregar, reemplazar } = useCarrito()
  const [detalle, setDetalle] = useState(null)
  const [eleccion, setEleccion] = useState(null)
  const [error, setError] = useState(null)
  const [enviando, setEnviando] = useState(false)

  useEffect(() => {
    dialogo.current?.showModal()
  }, [])

  useEffect(() => {
    let vigente = true
    obtenerDetalleProducto(producto.id)
      .then((datos) => {
        if (!vigente) return
        setDetalle(datos)
        setEleccion(eleccionInicial(datos, linea))
      })
      .catch((err) => {
        if (vigente) setError(interpretarError(err).general)
      })
    return () => {
      vigente = false
    }
  }, [producto.id, linea])

  function cambiar(campos) {
    setError(null)
    setEleccion((actual) => ({ ...actual, ...campos }))
  }

  function alternarExclusion(id) {
    const exclusiones = new Set(eleccion.exclusiones)
    if (exclusiones.has(id)) exclusiones.delete(id)
    else exclusiones.add(id)
    cambiar({ exclusiones })
  }

  // Arma la línea con los datos que se muestran en el carrito.
  function armarLinea() {
    const tamano = detalle.tamanos.find((item) => item.id === eleccion.tamanoId) ?? null
    return {
      producto: {
        id: detalle.id,
        nombre: detalle.nombre,
        imagen: producto.imagen ?? null,
        precio_base: detalle.precio_base,
      },
      tamano: tamano && { id: tamano.id, nombre: tamano.nombre, precio_adicional: tamano.precio_adicional },
      adiciones: detalle.adiciones
        .filter((item) => eleccion.adiciones[item.adicion] > 0)
        .map((item) => ({
          adicion: item.adicion,
          nombre: item.nombre,
          precio: item.precio,
          cantidad: eleccion.adiciones[item.adicion],
        })),
      exclusiones: detalle.ingredientes
        .filter((item) => eleccion.exclusiones.has(item.id))
        .map((item) => ({ id: item.id, nombre: item.nombre })),
      cantidad: eleccion.cantidad,
    }
  }

  async function confirmar(evento) {
    evento.preventDefault()
    const nueva = armarLinea()
    // Si ya hay una línea igual, se suman: el stock se valida con la cantidad total.
    const igual = buscarLineaIgual(lineas, nueva, linea?.id)
    const total = nueva.cantidad + (igual?.cantidad ?? 0)

    setEnviando(true)
    setError(null)
    try {
      const { precio_unitario } = await validarLineaCarrito(sedeId, {
        ...lineaParaValidar(nueva),
        cantidad: total,
      })
      const confirmada = { ...nueva, precio_unitario }
      if (linea) reemplazar(linea.id, confirmada)
      else agregar(sedeId, confirmada)
      alAgregar?.(confirmada, Boolean(igual))
      dialogo.current?.close()
    } catch (err) {
      const { general, campos } = interpretarError(err)
      setError(Object.values(campos)[0] ?? general)
    } finally {
      setEnviando(false)
    }
  }

  const precioLinea = detalle && eleccion
    ? precioUnitario({ producto: detalle, ...armarLinea() }) * eleccion.cantidad
    : null
  const obligatorios = detalle?.ingredientes.filter((item) => !item.es_excluible) ?? []
  const excluibles = detalle?.ingredientes.filter((item) => item.es_excluible) ?? []
  const bloqueos = detalle && eleccion
    ? bloqueosPorInsumo({
        ingredientes: excluibles,
        adiciones: detalle.adiciones,
        cantidades: eleccion.adiciones,
        exclusiones: eleccion.exclusiones,
      })
    : { adiciones: {}, ingredientes: {} }
  // Una línea guardada antes de esta regla puede quitar y agregar el mismo insumo.
  const contradiccion = Object.keys(bloqueos.adiciones).some((id) => eleccion.adiciones[id] > 0)

  return (
    <dialog
      ref={dialogo}
      onClose={alCerrar}
      aria-labelledby="titulo-personalizar"
      className="m-auto w-[calc(100%-2rem)] max-w-lg rounded-xl border border-borde bg-superficie p-0 text-texto backdrop:bg-black/50"
    >
      <form onSubmit={confirmar} className="flex max-h-[85vh] flex-col">
        <header className="flex items-start justify-between gap-3 border-b border-borde p-4">
          <div>
            <h2 id="titulo-personalizar" className="text-xl font-bold">
              {producto.nombre}
            </h2>
            {detalle?.descripcion && <p className="text-sm text-texto-suave">{detalle.descripcion}</p>}
          </div>
          <Boton variante="fantasma" onClick={() => dialogo.current?.close()} aria-label="Cerrar">
            ✕
          </Boton>
        </header>

        <div className="flex flex-col gap-5 overflow-y-auto p-4">
          {!detalle && !error && <p className="text-texto-suave">Cargando opciones…</p>}

          {detalle && eleccion && (
            <>
              {detalle.tamanos.length > 0 && (
                <fieldset className="flex flex-col gap-2">
                  <legend className="mb-2 font-semibold">Tamaño</legend>
                  {detalle.tamanos.map((tamano) => (
                    <label
                      key={tamano.id}
                      className="flex min-h-11 cursor-pointer items-center justify-between gap-3 rounded-lg border border-borde px-3 has-[:checked]:border-marca"
                    >
                      <span className="flex items-center gap-3">
                        <input
                          type="radio"
                          name="tamano"
                          className="h-5 w-5 accent-marca"
                          checked={eleccion.tamanoId === tamano.id}
                          onChange={() => cambiar({ tamanoId: tamano.id })}
                        />
                        {tamano.nombre}
                      </span>
                      {/* Precio del producto en ese tamaño, no la diferencia sobre el base. */}
                      <span className="text-sm text-texto-suave">
                        {formatearPrecio(Number(detalle.precio_base) + Number(tamano.precio_adicional))}
                      </span>
                    </label>
                  ))}
                </fieldset>
              )}

              {detalle.adiciones.length > 0 && (
                <fieldset className="flex flex-col gap-2">
                  <legend className="mb-2 font-semibold">Adiciones</legend>
                  {detalle.adiciones.map((item) => (
                    <div key={item.adicion} className="flex items-center justify-between gap-3">
                      <div>
                        <p className="font-medium">{item.nombre}</p>
                        <p className="text-sm text-texto-suave">
                          + {formatearPrecio(item.precio)} · máximo {item.max_cantidad}
                        </p>
                        {bloqueos.adiciones[item.adicion] && (
                          <p className="text-sm text-aviso">
                            Quitaste {bloqueos.adiciones[item.adicion].nombre.toLowerCase()} de los ingredientes base.
                          </p>
                        )}
                      </div>
                      <Contador
                        etiqueta={item.nombre}
                        valor={eleccion.adiciones[item.adicion]}
                        // Bloqueada: no se puede subir, pero sí bajar para deshacer la contradicción.
                        maximo={bloqueos.adiciones[item.adicion] ? eleccion.adiciones[item.adicion] : item.max_cantidad}
                        alCambiar={(valor) =>
                          cambiar({ adiciones: { ...eleccion.adiciones, [item.adicion]: valor } })
                        }
                      />
                    </div>
                  ))}
                </fieldset>
              )}

              {detalle.ingredientes.length > 0 && (
                <fieldset className="flex flex-col gap-2">
                  <legend className="mb-2 font-semibold">Ingredientes base</legend>
                  {excluibles.map((item) => (
                    <Casilla
                      key={item.id}
                      etiqueta={`Quitar ${item.nombre}`}
                      descripcion={
                        bloqueos.ingredientes[item.id] &&
                        `No se puede quitar: agregaste ${bloqueos.ingredientes[item.id].nombre.toLowerCase()}.`
                      }
                      // Bloqueado: no se puede marcar, pero sí desmarcar.
                      disabled={Boolean(bloqueos.ingredientes[item.id]) && !eleccion.exclusiones.has(item.id)}
                      checked={eleccion.exclusiones.has(item.id)}
                      onChange={() => alternarExclusion(item.id)}
                    />
                  ))}
                  {obligatorios.length > 0 && (
                    <p className="text-sm text-texto-suave">
                      Siempre incluye: {obligatorios.map((item) => item.nombre).join(', ')}.
                    </p>
                  )}
                </fieldset>
              )}

              <div className="flex items-center justify-between gap-3">
                <span className="font-semibold">Cantidad</span>
                <Contador
                  etiqueta="Cantidad"
                  valor={eleccion.cantidad}
                  minimo={1}
                  alCambiar={(cantidad) => cambiar({ cantidad })}
                />
              </div>
            </>
          )}

          {contradiccion && (
            <Alerta tipo="aviso" titulo="Estás quitando un ingrediente base y agregando su adición.">
              Baja la adición a 0 o desmarca el ingrediente para poder guardar.
            </Alerta>
          )}
          {error && <Alerta tipo="error" titulo={error} />}
        </div>

        <footer className="flex items-center justify-between gap-3 border-t border-borde p-4">
          <p className="text-lg font-bold">{precioLinea !== null && formatearPrecio(precioLinea)}</p>
          <Boton tipo="submit" cargando={enviando} disabled={!detalle || contradiccion}>
            {linea ? 'Guardar cambios' : 'Agregar al carrito'}
          </Boton>
        </footer>
      </form>
    </dialog>
  )
}
