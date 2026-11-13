import { useEffect, useState } from 'react'
import { listarDirecciones } from '../api/direcciones.js'
import { validarCoberturaDireccion } from '../api/sedes.js'

// Datos de la zona donde cae la dirección principal del cliente (o la primera):
// el pedido mínimo (HU-57) y la tarifa de domicilio (HU-22).
// Mientras carga, o si no se puede determinar, devuelve null en los dos: en ese caso
// el carrito no bloquea nada, no inventa un domicilio y el backend valida al confirmar.
export function useZonaEntrega() {
  const [zona, setZona] = useState(null)

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
        if (activo && cobertura?.cubierto) {
          setZona({
            pedidoMinimo: cobertura.sede.pedido_minimo ?? 0,
            tarifaDomicilio: cobertura.sede.tarifa_domicilio ?? null,
          })
        }
      })
      .catch(() => {})
    return () => {
      activo = false
    }
  }, [])

  return { pedidoMinimo: zona?.pedidoMinimo ?? null, tarifaDomicilio: zona?.tarifaDomicilio ?? null }
}