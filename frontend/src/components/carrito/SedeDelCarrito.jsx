import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { listarSedesMenu } from '../../api/menu.js'
import { guardarSede } from '../../utils/sedeElegida.js'
import { buscarSede, nombreSede } from '../../utils/sedeCarrito.js'

// Sede a la que se le está comprando. El carrito puede venir de otro dispositivo
// (HU-21) o cambiar de sede al confirmar (HU-62), por eso se muestra antes de pagar.
// - variante "encabezado": debajo del título del carrito, con enlace al menú de esa sede
// - variante "resumen": una fila más en el resumen de "Confirmar pedido"
// Si no se puede cargar el nombre, no muestra nada (el pedido sigue funcionando).
export default function SedeDelCarrito({ sedeId, variante = 'encabezado' }) {
  const [sedes, setSedes] = useState([])

  useEffect(() => {
    let vigente = true
    listarSedesMenu()
      .then((datos) => vigente && setSedes(Array.isArray(datos) ? datos : (datos?.results ?? [])))
      .catch(() => vigente && setSedes([]))
    return () => {
      vigente = false
    }
  }, [])

  const sede = buscarSede(sedes, sedeId)
  if (!sede) return null

  if (variante === 'resumen') {
    return (
      <div className="flex justify-between gap-3 text-sm">
        <span className="text-texto-suave">Pides en:</span>
        <span className="text-right font-semibold">{nombreSede(sede)}</span>
      </div>
    )
  }

  return (
    <p className="text-texto-suave">
      Pides en <strong className="font-semibold text-texto">{nombreSede(sede)}</strong>
      {' · '}
      <Link
        to="/menu"
        onClick={() => guardarSede(sede.id)}
        className="font-medium text-marca underline-offset-2 hover:underline"
      >
        Ver menú de esta sede
      </Link>
    </p>
  )
}
