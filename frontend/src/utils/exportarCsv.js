// HU-73 · Exportar los reportes a CSV (se genera en el navegador con los datos ya consultados)

// Marca de orden de bytes: sin ella Excel abre el archivo como ANSI y daña las tildes y la ñ
const BOM = '﻿'

// RFC 4180: el campo va entre comillas si trae comillas, comas o saltos de línea,
// y las comillas internas se duplican. null o undefined -> celda vacía
function escaparCampo(valor) {
  if (valor === null || valor === undefined) return ''
  const texto = String(valor)
  if (!/[",\r\n]/.test(texto)) return texto
  return `"${texto.replaceAll('"', '""')}"`
}

// columnas = [{ titulo, valor: (fila) => ... }]. Devuelve el texto con encabezado y filas separadas por \r\n
export function generarCsv(columnas, filas) {
  const encabezado = columnas.map((c) => escaparCampo(c.titulo)).join(',')
  const lineas = filas.map((fila) => columnas.map((c) => escaparCampo(c.valor(fila))).join(','))
  return [encabezado, ...lineas].join('\r\n') + '\r\n'
}

// Descarga el texto como archivo .csv en UTF-8 (con BOM) usando un enlace temporal
export function descargarCsv(nombreArchivo, texto) {
  const archivo = new Blob([BOM + texto], { type: 'text/csv;charset=utf-8' })
  const url = URL.createObjectURL(archivo)
  const enlace = document.createElement('a')
  enlace.href = url
  enlace.download = nombreArchivo
  document.body.appendChild(enlace)
  enlace.click()
  enlace.remove()
  URL.revokeObjectURL(url)
}

// ('ventas-producto', '2026-11-20', '2026-11-26') -> "ventas-producto_2026-11-20_2026-11-26.csv"
export function nombreArchivoReporte(tipo, desde, hasta) {
  return `${tipo}_${desde}_${hasta}.csv`
}
