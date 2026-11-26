import { descargarCsv, generarCsv, nombreArchivoReporte } from '../../utils/exportarCsv.js'
import Boton from '../ui/Boton.jsx'

// HU-73 · Descarga en CSV las filas de un reporte ya consultado.
// `datos` es la respuesta del backend (trae desde, hasta y sin_datos); `filas` son las de la tabla.
export default function BotonExportar({ tipo, datos, columnas, filas, className = '' }) {
  const sinDatos = !datos || datos.sin_datos || !filas || filas.length === 0

  function exportar() {
    descargarCsv(nombreArchivoReporte(tipo, datos.desde, datos.hasta), generarCsv(columnas, filas))
  }

  return (
    <Boton variante="secundario" className={className} disabled={sinDatos} onClick={exportar}>
      Exportar CSV
    </Boton>
  )
}
