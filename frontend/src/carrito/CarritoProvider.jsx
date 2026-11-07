import { useCallback, useMemo, useState } from 'react'
import { useAuth } from '../auth/useAuth.js'
import {
  actualizarCantidad,
  agregarLinea,
  cantidadArticulos,
  claveCarrito,
  domicilioCarrito,
  eliminarLinea,
  reemplazarLinea,
  subtotalCarrito,
  totalCarrito,
  TARIFA_DOMICILIO_PROVISIONAL_DEFAULT,
} from '../utils/carrito.js'
import { CarritoContext } from './CarritoContext.js'

const VACIO = { sedeId: null, lineas: [] }

// El carrito vive en el navegador (HU-21), uno por cuenta de cliente: el backend
// solo valida cada línea. Sincronizarlo entre dispositivos queda para el producto final.
function leerCarrito(clave) {
  if (!clave) return VACIO
  try {
    const texto = localStorage.getItem(clave)
    const guardado = texto ? JSON.parse(texto) : null
    return Array.isArray(guardado?.lineas) ? guardado : VACIO
  } catch {
    // Almacenamiento bloqueado o dato corrupto: se empieza con el carrito vacío.
    return VACIO
  }
}

function guardarCarrito(clave, carrito) {
  if (!clave) return
  try {
    localStorage.setItem(clave, JSON.stringify(carrito))
  } catch {
    // Sin almacenamiento disponible: el carrito dura mientras la pestaña esté abierta.
  }
}

function nuevoId() {
  return globalThis.crypto?.randomUUID?.() ?? `${Date.now()}-${Math.random()}`
}

// El carrito pertenece a una sede: la disponibilidad y el stock dependen de ella.
// Se agrega tarifaSede con valor por defecto en los props
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
      actualizar((actual) => ({
        sedeId,
        lineas: agregarLinea(actual.sedeId === sedeId ? actual.lineas : [], { ...linea, id: nuevoId() }),
      })),
    [actualizar],
  )

  const reemplazar = useCallback(
    (id, linea) => actualizar((actual) => ({ ...actual, lineas: reemplazarLinea(actual.lineas, id, linea) })),
    [actualizar],
  )

  const cambiarCantidad = useCallback(
    (id, cantidad) =>
      actualizar((actual) => ({ ...actual, lineas: actualizarCantidad(actual.lineas, id, cantidad) })),
    [actualizar],
  )

  const eliminar = useCallback(
    (id) => actualizar((actual) => ({ ...actual, lineas: eliminarLinea(actual.lineas, id) })),
    [actualizar],
  )

  const vaciar = useCallback(() => actualizar(() => VACIO), [actualizar])

  // Cálculo de subtotales y totales usando tarifaSede
  const subtotal = useMemo(() => subtotalCarrito(carrito.lineas), [carrito.lineas])
  const costoDomicilio = useMemo(() => domicilioCarrito(subtotal, tarifaSede), [subtotal, tarifaSede])
  const total = useMemo(() => totalCarrito(subtotal, costoDomicilio), [subtotal, costoDomicilio])

  const valor = useMemo(
    () => ({
      sedeId: carrito.sedeId,
      lineas: carrito.lineas,
      subtotal,
      costoDomicilio,
      total,
      articulos: cantidadArticulos(carrito.lineas),
      agregar,
      reemplazar,
      cambiarCantidad,
      eliminar,
      vaciar,
    }),
    [carrito, subtotal, costoDomicilio, total, agregar, reemplazar, cambiarCantidad, eliminar, vaciar],
  )

  return <CarritoContext.Provider value={valor}>{children}</CarritoContext.Provider>
}
