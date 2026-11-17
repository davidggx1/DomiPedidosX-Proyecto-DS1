import { useCallback, useMemo, useState } from 'react'
import { useAuth } from '../auth/useAuth.js'
import {
  actualizarCantidad,
  agregarLinea,
  calcularDescuentoPromocion,
  cantidadArticulos,
  claveCarrito,
  domicilioCarrito,
  eliminarLinea,
  quitarLineasRetiradas,
  reemplazarLinea,
  subtotalCarrito,
  totalCarritoConDescuento,
  TARIFA_DOMICILIO_PROVISIONAL_DEFAULT,
} from '../utils/carrito.js'
import { CarritoContext } from './CarritoContext.js'

const VACIO = { sedeId: null, lineas: [], promocion: null }

function leerCarrito(clave) {
  if (!clave) return VACIO
  try {
    const texto = localStorage.getItem(clave)
    const guardado = texto ? JSON.parse(texto) : null
    if (!Array.isArray(guardado?.lineas)) return VACIO
    return {
      sedeId: guardado.sedeId ?? null,
      lineas: guardado.lineas,
      promocion: guardado.promocion ?? null,
    }
  } catch {
    return VACIO
  }
}

function guardarCarrito(clave, carrito) {
  if (!clave) return
  try {
    localStorage.setItem(clave, JSON.stringify(carrito))
  } catch {
    // Sin almacenamiento disponible
  }
}

function nuevoId() {
  return globalThis.crypto?.randomUUID?.() ?? `${Date.now()}-${Math.random()}`
}

export default function CarritoProvider({ children, tarifaSede = TARIFA_DOMICILIO_PROVISIONAL_DEFAULT }) {
  const { usuario } = useAuth()
  const clave = claveCarrito(usuario)
  const [estado, setEstado] = useState(() => ({ clave, carrito: leerCarrito(clave) }))

  if (estado.clave !== clave) {
    setEstado({ clave, carrito: leerCarrito(clave) })
  }
  const carrito = estado.clave === clave ? estado.carrito : leerCarrito(clave)

  const actualizar = useCallback((cambio) => {
    setEstado((actual) => {
      const nuevo = cambio(actual.carrito)
      guardarCarrito(actual.clave, nuevo)
      return { ...actual, carrito: nuevo }
    })
  }, [])

  const agregar = useCallback(
    (sedeId, linea) =>
      actualizar((actual) => {
        const mismaSede = actual.sedeId === sedeId
        return {
          sedeId,
          lineas: agregarLinea(mismaSede ? actual.lineas : [], { ...linea, id: nuevoId() }),
          promocion: mismaSede ? actual.promocion : null,
        }
      }),
    [actualizar],
  )

  const reemplazar = useCallback(
    (id, linea) =>
      actualizar((actual) => ({ ...actual, lineas: reemplazarLinea(actual.lineas, id, linea) })),
    [actualizar],
  )

  const cambiarCantidad = useCallback(
    (id, cantidad) =>
      actualizar((actual) => {
        const lineas = actualizarCantidad(actual.lineas, id, cantidad)
        return { ...actual, lineas, promocion: lineas.length > 0 ? actual.promocion : null }
      }),
    [actualizar],
  )

  const eliminar = useCallback(
    (id) =>
      actualizar((actual) => {
        const lineas = eliminarLinea(actual.lineas, id)
        return { ...actual, lineas, promocion: lineas.length > 0 ? actual.promocion : null }
      }),
    [actualizar],
  )

  const quitarProductos = useCallback(
    (productoIds) =>
      actualizar((actual) => {
        const lineas = quitarLineasRetiradas(actual.lineas, productoIds).lineas
        return { ...actual, lineas, promocion: lineas.length > 0 ? actual.promocion : null }
      }),
    [actualizar],
  )

  // HU-65: Aplica una promoción (reemplaza cualquier cupón previo: no acumulables)
  const aplicarPromocion = useCallback(
    (promocion) => actualizar((actual) => ({ ...actual, promocion })),
    [actualizar],
  )

  // HU-65: Remueve el cupón y restaura el precio original
  const quitarPromocion = useCallback(
    () => actualizar((actual) => ({ ...actual, promocion: null })),
    [actualizar],
  )

  const trasladarASede = useCallback(
    (nuevaSedeId, lineas) => actualizar(() => ({ sedeId: nuevaSedeId, lineas, promocion: null })),
    [actualizar],
  )

  const vaciar = useCallback(() => actualizar(() => VACIO), [actualizar])

  const subtotal = useMemo(() => subtotalCarrito(carrito.lineas), [carrito.lineas])
  const descuento = useMemo(
    () => calcularDescuentoPromocion(subtotal, carrito.promocion),
    [subtotal, carrito.promocion],
  )
  const costoDomicilio = useMemo(() => domicilioCarrito(subtotal, tarifaSede), [subtotal, tarifaSede])
  const total = useMemo(
    () => totalCarritoConDescuento(subtotal, descuento, costoDomicilio),
    [subtotal, descuento, costoDomicilio],
  )

  const valor = useMemo(
    () => ({
      sedeId: carrito.sedeId,
      lineas: carrito.lineas,
      promocion: carrito.promocion,
      subtotal,
      descuento,
      costoDomicilio,
      total,
      articulos: cantidadArticulos(carrito.lineas),
      agregar,
      reemplazar,
      cambiarCantidad,
      eliminar,
      quitarProductos,
      aplicarPromocion,
      quitarPromocion,
      trasladarASede,
      vaciar,
    }),
    [
      carrito,
      subtotal,
      descuento,
      costoDomicilio,
      total,
      agregar,
      reemplazar,
      cambiarCantidad,
      eliminar,
      quitarProductos,
      aplicarPromocion,
      quitarPromocion,
      trasladarASede,
      vaciar,
    ],
  )

  return <CarritoContext.Provider value={valor}>{children}</CarritoContext.Provider>
}