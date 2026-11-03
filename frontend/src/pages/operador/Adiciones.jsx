import { useEffect, useState } from 'react'
import {
  actualizarAdicion,
  eliminarAdicion,
  listarAdiciones,
  listarInsumos,
  listarProductosOpciones,
} from '../../api/menu.js'
import { interpretarError } from '../../api/errores.js'
import { formatearPrecio } from '../../utils/formato.js'
import AdicionesProducto from '../../components/menu/AdicionesProducto.jsx'
import FormularioAdicion from '../../components/menu/FormularioAdicion.jsx'
import Alerta from '../../components/ui/Alerta.jsx'
import Boton from '../../components/ui/Boton.jsx'
import Casilla from '../../components/ui/Casilla.jsx'
import Selector from '../../components/ui/Selector.jsx'
import Tarjeta from '../../components/ui/Tarjeta.jsx'

// HU-76 · Adiciones de un producto (vista del operador de sede).
export default function Adiciones() {
  const [adiciones, setAdiciones] = useState([])
  const [insumos, setInsumos] = useState([])
  const [productos, setProductos] = useState([])
  const [cargando, setCargando] = useState(true)
  const [errorCarga, setErrorCarga] = useState(null)
  const [mostrarEliminadas, setMostrarEliminadas] = useState(false)
  const [recarga, setRecarga] = useState(0)
  const [editando, setEditando] = useState(null)
  const [mensaje, setMensaje] = useState(null)
  const [productoId, setProductoId] = useState('')

  // Catálogo de adiciones: se recarga al cambiar el filtro o después de guardar.
  useEffect(() => {
    let vigente = true
    listarAdiciones({ activa: mostrarEliminadas ? undefined : true })
      .then((datos) => {
        if (!vigente) return
        setAdiciones(datos)
        setErrorCarga(null)
      })
      .catch((err) => {
        if (vigente) setErrorCarga(interpretarError(err).general)
      })
      .finally(() => {
        if (vigente) setCargando(false)
      })
    return () => {
      vigente = false
    }
  }, [mostrarEliminadas, recarga])

  // Insumos y productos para los selectores: se cargan una sola vez.
  useEffect(() => {
    let vigente = true
    Promise.all([listarInsumos(), listarProductosOpciones()])
      .then(([listaInsumos, listaProductos]) => {
        if (!vigente) return
        setInsumos(listaInsumos)
        setProductos(listaProductos)
      })
      .catch((err) => {
        if (vigente) setErrorCarga(interpretarError(err).general)
      })
    return () => {
      vigente = false
    }
  }, [])

  function recargar() {
    setRecarga((valor) => valor + 1)
  }

  function alGuardar(adicion, fueEdicion) {
    setMensaje({
      tipo: 'exito',
      texto: fueEdicion
        ? `Se guardaron los cambios de "${adicion.nombre}". Los pedidos anteriores conservan su precio.`
        : `Se creó la adición "${adicion.nombre}".`,
    })
    setEditando(null)
    recargar()
  }

  async function eliminar(adicion) {
    const confirmado = window.confirm(
      `¿Eliminar la adición "${adicion.nombre}"? Los clientes dejarán de verla; los pedidos anteriores no cambian.`,
    )
    if (!confirmado) return
    try {
      await eliminarAdicion(adicion.id)
      if (editando?.id === adicion.id) setEditando(null)
      setMensaje({ tipo: 'exito', texto: `Se eliminó la adición "${adicion.nombre}".` })
      recargar()
    } catch (err) {
      setMensaje({ tipo: 'error', texto: interpretarError(err).general })
    }
  }

  async function restaurar(adicion) {
    try {
      await actualizarAdicion(adicion.id, { activa: true })
      setMensaje({ tipo: 'exito', texto: `Se restauró la adición "${adicion.nombre}".` })
      recargar()
    } catch (err) {
      const { general, campos } = interpretarError(err)
      setMensaje({ tipo: 'error', texto: campos.nombre ?? general })
    }
  }

  const opcionesProducto = productos.map((producto) => ({
    valor: String(producto.id),
    etiqueta: `${producto.nombre} · ${producto.categoria_nombre}`,
  }))

  return (
    <div className="flex flex-col gap-6">
      <header>
        <h1 className="text-2xl font-bold">Adiciones</h1>
        <p className="text-texto-suave">
          Extras que el cliente puede sumar a un producto, como queso o tocineta.
        </p>
      </header>

      {mensaje && <Alerta tipo={mensaje.tipo} titulo={mensaje.texto} />}
      {errorCarga && <Alerta tipo="error" titulo={errorCarga} />}

      <div className="grid gap-6 lg:grid-cols-[minmax(0,2fr)_minmax(0,3fr)]">
        <Tarjeta>
          <FormularioAdicion
            key={editando?.id ?? 'nueva'}
            adicion={editando}
            insumos={insumos}
            alGuardar={alGuardar}
            alCancelar={() => setEditando(null)}
          />
        </Tarjeta>

        <Tarjeta titulo="Catálogo de adiciones">
          <Casilla
            etiqueta="Mostrar también las eliminadas"
            checked={mostrarEliminadas}
            onChange={(evento) => setMostrarEliminadas(evento.target.checked)}
            className="mb-4"
          />

          {cargando ? (
            <p className="text-texto-suave">Cargando adiciones…</p>
          ) : adiciones.length === 0 ? (
            <p className="text-texto-suave">Todavía no hay adiciones registradas.</p>
          ) : (
            <ul className="flex flex-col gap-2">
              {adiciones.map((adicion) => (
                <li
                  key={adicion.id}
                  className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-borde bg-fondo px-3 py-2"
                >
                  <div>
                    <p className="font-medium">
                      {adicion.nombre}{' '}
                      <span className="text-texto-suave">+{formatearPrecio(adicion.precio)}</span>
                    </p>
                    <p className="text-sm text-texto-suave">Consume: {adicion.insumo_nombre}</p>
                    {!adicion.activa && <p className="text-sm text-aviso">Eliminada</p>}
                  </div>
                  <div className="flex gap-2">
                    {adicion.activa ? (
                      <>
                        <Boton
                          variante="secundario"
                          onClick={() => setEditando(adicion)}
                          aria-label={`Editar ${adicion.nombre}`}
                        >
                          Editar
                        </Boton>
                        <Boton
                          variante="peligro"
                          onClick={() => eliminar(adicion)}
                          aria-label={`Eliminar ${adicion.nombre}`}
                        >
                          Eliminar
                        </Boton>
                      </>
                    ) : (
                      <Boton
                        variante="secundario"
                        onClick={() => restaurar(adicion)}
                        aria-label={`Restaurar ${adicion.nombre}`}
                      >
                        Restaurar
                      </Boton>
                    )}
                  </div>
                </li>
              ))}
            </ul>
          )}
        </Tarjeta>
      </div>

      <Tarjeta titulo="Adiciones por producto">
        <Selector
          etiqueta="Producto"
          opciones={opcionesProducto}
          value={productoId}
          onChange={(evento) => setProductoId(evento.target.value)}
          textoVacio="Selecciona un producto"
          className="mb-4 max-w-md"
        />
        {productoId && (
          <AdicionesProducto key={`${productoId}-${recarga}`} productoId={productoId} />
        )}
      </Tarjeta>
    </div>
  )
}
