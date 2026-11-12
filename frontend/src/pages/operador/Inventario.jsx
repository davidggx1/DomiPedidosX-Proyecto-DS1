import { useState } from 'react'
import PanelStockBajo from '../../components/inventario/PanelStockBajo.jsx'
import SeccionExistencias from '../../components/inventario/SeccionExistencias.jsx'
import Boton from '../../components/ui/Boton.jsx'
import { TIPOS_EXISTENCIAS } from '../../utils/existencias.js'

// HU-14 · Registrar y actualizar existencias de la sede (vista del operador)
export default function Inventario() {
  const [tipo, setTipo] = useState('productos')

  return (
    <div className="flex flex-col gap-6">
      <header>
        <h1 className="text-2xl font-bold">Inventario</h1>
        <p className="text-texto-suave">
          Registra y ajusta las existencias de tu sede. El menú del cliente se actualiza con cada
          cambio.
        </p>
      </header>

      <PanelStockBajo />

      <div role="group" aria-label="Tipo de existencias" className="flex flex-wrap gap-2">
        {Object.entries(TIPOS_EXISTENCIAS).map(([clave, config]) => (
          <Boton
            key={clave}
            variante={tipo === clave ? 'primario' : 'secundario'}
            aria-pressed={tipo === clave}
            onClick={() => setTipo(clave)}
          >
            {config.titulo}
          </Boton>
        ))}
      </div>

      <SeccionExistencias key={tipo} tipo={tipo} />
    </div>
  )
}
