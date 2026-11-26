import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { guardarCarritoServidor, obtenerCarritoGuardado } from '../api/usuarios.js'
import { useAuth } from '../auth/useAuth.js'
import {
  actualizarCantidad,
  agregarLinea,
  calcularDescuentoPromocion,
  cantidadArticulos,
  claveCarrito,
  domicilioCarrito,
  elegirCarritoInicial,
  eliminarLinea,
  quitarLineasRetiradas,
  reemplazarLinea,
  subtotalCarrito,
  totalCarritoConDescuento,
  TARIFA_DOMICILIO_PROVISIONAL_DEFAULT,
} from '../utils/carrito.js'
import { CarritoContext } from './CarritoContext.js'

const VACIO = { sedeId: null, lineas: [], promocion: null }
// HU-21: varios cambios seguidos (p. ej. subir la cantidad 3 veces) mandan un solo PUT
const ESPERA_GUARDADO_MS = 600

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

  // HU-21: el carrito también se guarda en el servidor para verlo en cualquier dispositivo.
  // localStorage queda como copia local: si el servidor no responde, el carrito sigue funcionando.
  const temporizador = useRef(null)
  const sincronizado = useRef(null) // clave del cliente cuyo carrito ya se cargó del servidor
  const cambioPendiente = useRef(false) // el cliente cambió el carrito antes de que cargara
  const carritoRef = useRef(carrito)
  useEffect(() => {
    carritoRef.current = carrito
  }, [carrito])

  const subirAlServidor = useCallback((nuevo) => {
    clearTimeout(temporizador.current)
    temporizador.current = setTimeout(() => {
      guardarCarritoServidor(nuevo).catch(() => {
        // sin conexión: queda en el navegador y se vuelve a enviar con el siguiente cambio
      })
    }, ESPERA_GUARDADO_MS)
  }, [])

  // Al iniciar sesión (o cambiar de cliente) se trae el carrito guardado en el servidor
  useEffect(() => {
    if (!clave) return undefined
    let vigente = true
    sincronizado.current = null
    cambioPendiente.current = false

    obtenerCarritoGuardado()
      .then((servidor) => {
        if (!vigente) return
        const local = carritoRef.current
        const { carrito: elegido, subirLocal } = cambioPendiente.current
          ? { carrito: local, subirLocal: true }
          : elegirCarritoInicial(local, servidor)
        guardarCarrito(clave, elegido)
        setEstado((actual) => (actual.clave === clave ? { ...actual, carrito: elegido } : actual))
        sincronizado.current = clave
        if (subirLocal) subirAlServidor(elegido)
      })
      .catch(() => {
        // Si no se pudo leer, no se sube nada para no borrar el carrito guardado desde
        // otro dispositivo: el carrito queda solo en el navegador hasta la próxima visita.
      })

    return () => {
      vigente = false
      clearTimeout(temporizador.current)
    }
  }, [clave, subirAlServidor])

  const actualizar = useCallback(
    (cambio) => {
      setEstado((actual) => {
        const nuevo = cambio(actual.carrito)
        guardarCarrito(actual.clave, nuevo)
        if (sincronizado.current === actual.clave) subirAlServidor(nuevo)
        else cambioPendiente.current = true
        return { ...actual, carrito: nuevo }
      })
    },
    [subirAlServidor],
  )

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

  // HU-26: reemplaza el carrito por las líneas de un pedido anterior (ya validadas por el backend)
  const cargarPedido = useCallback(
    (nuevaSedeId, lineas) =>
      actualizar(() => ({
        sedeId: nuevaSedeId,
        lineas: lineas.reduce((acumuladas, linea) => agregarLinea(acumuladas, { ...linea, id: nuevoId() }), []),
        promocion: null,
      })),
    [actualizar],
  )

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
      cargarPedido,
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
      cargarPedido,
    ],
  )

  return <CarritoContext.Provider value={valor}>{children}</CarritoContext.Provider>
}