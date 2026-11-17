import { useEffect, useRef, useState } from 'react'
import { validarCarrito } from '../api/menu.js'
import { quitarLineasRetiradas, textoLineasQuitadas } from '../utils/carrito.js'
import { useCarrito } from './useCarrito.js'

// HU-79: a product deleted from the menu has to leave the carts that still have it.
// The cart lives in the browser, so it is checked with the server when the page
// opens and when the products of the cart change (not when only a quantity does).
// Returns the notice for the client, or null
export function useLimpiarCarrito() {
  const { sedeId, lineas, quitarProductos } = useCarrito()
  const [aviso, setAviso] = useState(null)

  const lineasRef = useRef(lineas)
  useEffect(() => {
    lineasRef.current = lineas
  }, [lineas])

  // ids of the products as text, so the effect does not run again for a new quantity
  const productos = [...new Set(lineas.filter((l) => Boolean(l.producto)).map((l) => l.producto.id))]
    .sort((a, b) => a - b)
    .join(',')

  useEffect(() => {
    if (!sedeId || !productos) return undefined
    let vigente = true

    validarCarrito(sedeId, productos.split(',').map(Number))
      .then(({ retirados = [] }) => {
        if (!vigente || retirados.length === 0) return
        const { quitadas } = quitarLineasRetiradas(lineasRef.current, retirados)
        quitarProductos(retirados)
        setAviso(textoLineasQuitadas(quitadas))
      })
      .catch(() => {
        // no answer: the cart stays as it is and confirming the order checks it again
      })

    return () => {
      vigente = false
    }
  }, [sedeId, productos, quitarProductos])

  return aviso
}
