import { useEffect, useState } from 'react'
import { listarExistencias, quitarExistencias } from '../../api/inventario.js'
import { listarInsumos, listarProductosOpciones } from '../../api/menu.js'
import { interpretarError } from '../../api/errores.js'
import {
  TIPOS_EXISTENCIAS,
  detalleFila,
  estaAgotado,
  textoStock,
} from '../../utils/existencias.js'
import { abreviaturaUnidad } from '../../utils/unidades.js'
import Alerta from '../ui/Alerta.jsx'
import Boton from '../ui/Boton.jsx'
import Tarjeta from '../ui/Tarjeta.jsx'
import FormularioExistencias from './FormularioExistencias.jsx'

// Items that can be stocked, in the shape the selector needs
async function cargarCatalogo(tipo) {
  if (tipo === 'productos') {
    const productos = await listarProductosOpciones()
    return productos.map((producto) => ({
      id: producto.id,
      etiqueta: `${producto.nombre} · ${producto.categoria_nombre}`,
    }))
  }
  const insumos = await listarInsumos({ activo: true })
  return insumos.map((insumo) => ({
    id: insumo.id,
    etiqueta: `${insumo.nombre} (${abreviaturaUnidad(insumo.unidad_medida)})`,
    unidad: insumo.unidad_medida,
  }))
}

// Form and list of the stock of one kind (products or ingredients) in the operador's sede
// The parent should change the `key` when `tipo` changes to reset everything
export default function SeccionExistencias({ tipo }) {
  const config = TIPOS_EXISTENCIAS[tipo]
  const [filas, setFilas] = useState([])
  const [catalogo, setCatalogo] = useState([])
  const [cargando, setCargando] = useState(true)
  const [errorCarga, setErrorCarga] = useState(null)
  const [recarga, setRecarga] = useState(0) // bump it to load the list again
  const [editando, setEditando] = useState(null)
  const [mensaje, setMensaje] = useState(null)

  useEffect(() => {
    let vigente = true
    listarExistencias(tipo)
      .then((datos) => {
        if (!vigente) return
        setFilas(datos)
        setErrorCarga(null)
      })
      .catch((error) => {
        if (vigente) setErrorCarga(interpretarError(error).general)
      })
      .finally(() => {
        if (vigente) setCargando(false)
      })
    return () => {
      vigente = false
    }
  }, [tipo, recarga])

  useEffect(() => {
    let vigente = true
    cargarCatalogo(tipo)
      .then((datos) => {
        if (vigente) setCatalogo(datos)
      })
      .catch((error) => {
        if (vigente) setErrorCarga(interpretarError(error).general)
      })
    return () => {
      vigente = false
    }
  }, [tipo])

  const registrados = new Set(filas.map((fila) => fila[config.campoItem]))
  const opcionesItem = catalogo
    .filter((item) => !registrados.has(item.id))
    .map((item) => ({ valor: String(item.id), etiqueta: item.etiqueta, unidad: item.unidad }))

  function alGuardar(guardado, fueAjuste) {
    const nombre = config.nombre(guardado)
    setMensaje({
      tipo: 'exito',
      texto: fueAjuste
        ? `Se actualizaron las existencias de "${nombre}".`
        : `Se registraron las existencias de "${nombre}".`,
    })
    setEditando(null)
    setRecarga((numero) => numero + 1)
  }

  async function quitar(fila) {
    const nombre = config.nombre(fila)
    const consecuencia =
      tipo === 'productos'
        ? 'Dejará de ofrecerse en el menú de tu sede hasta que registres sus existencias otra vez.'
        : 'Se perderá su registro de existencias en tu sede.'
    if (!window.confirm(`¿Quitar "${nombre}" del inventario? ${consecuencia}`)) return
    try {
      await quitarExistencias(tipo, fila.id)
      if (editando?.id === fila.id) setEditando(null)
      setMensaje({ tipo: 'exito', texto: `Se quitó "${nombre}" del inventario de tu sede.` })
      setRecarga((numero) => numero + 1)
    } catch (error) {
      setMensaje({ tipo: 'error', texto: interpretarError(error).general })
    }
  }

  return (
    <div className="flex flex-col gap-4">
      {mensaje && <Alerta tipo={mensaje.tipo} titulo={mensaje.texto} />}
      {errorCarga && <Alerta tipo="error" titulo={errorCarga} />}

      <div className="grid gap-6 lg:grid-cols-[minmax(0,2fr)_minmax(0,3fr)]">
        <Tarjeta>
          <FormularioExistencias
            key={editando?.id ?? 'nuevo'}
            tipo={tipo}
            registro={editando}
            opcionesItem={opcionesItem}
            alGuardar={alGuardar}
            alCancelar={() => setEditando(null)}
          />
        </Tarjeta>

        <Tarjeta titulo={`Existencias de ${config.titulo.toLowerCase()}`}>
          {cargando ? (
            <p className="text-texto-suave">Cargando existencias…</p>
          ) : filas.length === 0 ? (
            <p className="text-texto-suave">
              Todavía no hay existencias registradas en tu sede. Registra la primera con el
              formulario.
            </p>
          ) : (
            <ul className="flex flex-col gap-2">
              {filas.map((fila) => (
                <li
                  key={fila.id}
                  className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-borde bg-fondo px-3 py-2"
                >
                  <div className="flex min-w-0 flex-col gap-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <p className="font-medium">{config.nombre(fila)}</p>
                      {estaAgotado(tipo, fila) && (
                        <span className="rounded-full border border-aviso px-2 py-0.5 text-xs font-medium text-aviso">
                          Agotado
                        </span>
                      )}
                    </div>
                    <p className="text-sm text-texto-suave">{detalleFila(tipo, fila)}</p>
                    <p className="text-sm">
                      Stock: <strong>{textoStock(tipo, fila, fila.stock_actual)}</strong>
                      <span className="text-texto-suave">
                        {' '}
                        · Mínimo: {textoStock(tipo, fila, fila.stock_minimo)}
                      </span>
                    </p>
                  </div>
                  <div className="flex gap-2">
                    <Boton
                      variante="secundario"
                      onClick={() => setEditando(fila)}
                      aria-label={`Ajustar ${config.nombre(fila)}`}
                    >
                      Ajustar
                    </Boton>
                    <Boton
                      variante="peligro"
                      onClick={() => quitar(fila)}
                      aria-label={`Quitar ${config.nombre(fila)}`}
                    >
                      Quitar
                    </Boton>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </Tarjeta>
      </div>
    </div>
  )
}
