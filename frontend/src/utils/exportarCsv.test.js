import { afterEach, describe, expect, it, vi } from 'vitest'
import { descargarCsv, generarCsv, nombreArchivoReporte } from './exportarCsv.js'

const columnas = [
  { titulo: 'Nombre', valor: (f) => f.nombre },
  { titulo: 'Ventas', valor: (f) => f.ventas },
]

describe('generarCsv (HU-73)', () => {
  it('escribe el encabezado y una línea por fila separadas por \\r\\n', () => {
    const filas = [
      { nombre: 'Hamburguesa', ventas: '12500.00' },
      { nombre: 'Limonada', ventas: '4000.00' },
    ]
    expect(generarCsv(columnas, filas)).toBe('Nombre,Ventas\r\nHamburguesa,12500.00\r\nLimonada,4000.00\r\n')
  })

  it('escapa comillas, comas y saltos de línea según RFC 4180', () => {
    const filas = [
      { nombre: 'Pizza "especial"', ventas: 1 },
      { nombre: 'Papas, grandes', ventas: 2 },
      { nombre: 'Combo\nfamiliar', ventas: 3 },
    ]
    expect(generarCsv(columnas, filas)).toBe(
      'Nombre,Ventas\r\n"Pizza ""especial""",1\r\n"Papas, grandes",2\r\n"Combo\nfamiliar",3\r\n',
    )
  })

  it('deja vacías las celdas null o undefined y conserva las tildes', () => {
    const filas = [{ nombre: 'Café con leche', ventas: null }, { nombre: 'Jugo' }]
    expect(generarCsv(columnas, filas)).toBe('Nombre,Ventas\r\nCafé con leche,\r\nJugo,\r\n')
  })

  it('sin filas devuelve solo el encabezado', () => {
    expect(generarCsv(columnas, [])).toBe('Nombre,Ventas\r\n')
  })
})

describe('descargarCsv (HU-73)', () => {
  afterEach(() => vi.unstubAllGlobals())

  it('descarga un Blob UTF-8 que empieza con BOM y usa el nombre pedido', async () => {
    const enlace = { click: vi.fn(), remove: vi.fn() }
    let archivo
    vi.stubGlobal('document', { createElement: () => enlace, body: { appendChild: vi.fn() } })
    vi.stubGlobal('URL', {
      createObjectURL: (blob) => {
        archivo = blob
        return 'blob:prueba'
      },
      revokeObjectURL: vi.fn(),
    })

    descargarCsv('ventas.csv', 'Nombre\r\nAñejo\r\n')

    expect(enlace.download).toBe('ventas.csv')
    expect(enlace.href).toBe('blob:prueba')
    expect(enlace.click).toHaveBeenCalledOnce()
    expect(URL.revokeObjectURL).toHaveBeenCalledWith('blob:prueba')
    expect(archivo.type).toBe('text/csv;charset=utf-8')
    const bytes = new Uint8Array(await archivo.arrayBuffer())
    expect([...bytes.slice(0, 3)]).toEqual([0xef, 0xbb, 0xbf])
    expect(new TextDecoder().decode(bytes)).toBe('Nombre\r\nAñejo\r\n')
  })
})

describe('nombreArchivoReporte (HU-73)', () => {
  it('une el tipo y el rango de fechas', () => {
    expect(nombreArchivoReporte('ventas-producto', '2026-11-20', '2026-11-26')).toBe(
      'ventas-producto_2026-11-20_2026-11-26.csv',
    )
  })
})
