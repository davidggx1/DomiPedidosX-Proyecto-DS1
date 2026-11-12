import { useEffect, useState } from 'react'
import { listarDirecciones } from '../api/direcciones.js'
import { validarCoberturaDireccion } from '../api/sedes.js'

// Pedido mínimo de la zona donde cae la dirección principal del cliente (o la primera).
// Devuelve null mientras carga o si no se puede determinar: en ese caso no se bloquea
// nada en el carrito y el backend valida al confirmar.
export function usePedidoMinimo() {
  const [pedidoMinimo, setPedidoMinimo] = useState(null)

  useEffect(() => {
    let activo = true
    listarDirecciones()
      .then((data) => {
        const lista = Array.isArray(data) ? data : (data?.results ?? [])
        const direccion = lista.find((d) => d.es_principal) ?? lista[0]
        if (!direccion) return null
        return validarCoberturaDireccion(direccion.latitud, direccion.longitud)
      })
      .then((cobertura) => {
        if (activo && cobertura?.cubierto) setPedidoMinimo(cobertura.sede.pedido_minimo ?? 0)
      })
      .catch(() => {})
    return () => {
      activo = false
    }
  }, [])

  return pedidoMinimo
}