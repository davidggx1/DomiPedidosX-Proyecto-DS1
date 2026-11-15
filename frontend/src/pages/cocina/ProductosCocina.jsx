import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { listarProductosCocina, marcarAgotado } from '../../api/cocina.js'
import { interpretarError } from '../../api/errores.js'
import Alerta from '../../components/ui/Alerta.jsx'
import Boton from '../../components/ui/Boton.jsx'
import CampoTexto from '../../components/ui/CampoTexto.jsx'
import Modal from '../../components/ui/Modal.jsx'
import { filtrarProductosCocina, productosReactivados } from '../../utils/cocina.js'
import { horaExacta } from '../../utils/tiempo.js'

// how often the list asks the server for changes (same as the kitchen board)
const INTERVALO_MS = 10000
// how long the confirmation and the "available again" notice stay on screen
const DURACION_MENSAJE_MS = 6000
const DURACION_REACTIVADOS_MS = 10000

// HU-17 · Products of the kitchen's sede. Cocina marks one as sold out when
// an ingredient runs out: it leaves the menu of the sede and the operator is warned.
// The list refreshes by itself and warns when the operator enables a product again
export default function ProductosCocina() {
  const [productos, setProductos] = useState(null)
  const [errorCarga, setErrorCarga] = useState(null)
  const [busqueda, setBusqueda] = useState('')
  const [confirmando, setConfirmando] = useState(null) // product waiting for confirmation
  const [enviando, setEnviando] = useState(false)
  const [mensaje, setMensaje] = useState(null)

  const [recarga, setRecarga] = useState(0) // bump it to load the list again
  const [reactivados, setReactivados] = useState([]) // names enabled again by the operator
  const anteriores = useRef(null) // last list received, to compare with the next one

  useEffect(() => {
    let vigente = true

    function cargar() {
      listarProductosCocina()
        .then((datos) => {
          if (!vigente) return
          const nuevos = productosReactivados(anteriores.current, datos)
          anteriores.current = datos
          setProductos(datos)
          setErrorCarga(null)
          if (nuevos.length > 0) {
            setReactivados((lista) => [...lista.filter((nombre) => !nuevos.includes(nombre)), ...nuevos])
            setMensaje(null) // an old "sold out" confirmation would contradict this notice
          }
        })
        .catch((error) => {
          if (vigente) setErrorCarga(interpretarError(error).general)
        })
    }

    cargar()
    const temporizador = setInterval(cargar, INTERVALO_MS)
    return () => {
      vigente = false
      clearInterval(temporizador)
    }
  }, [recarga])

  // the success confirmation closes by itself; errors stay until the next action
  useEffect(() => {
    if (mensaje?.tipo !== 'exito') return
    const temporizador = setTimeout(() => setMensaje(null), DURACION_MENSAJE_MS)
    return () => clearTimeout(temporizador)
  }, [mensaje])

  // the "available again" notice also closes by itself (or with "Entendido")
  useEffect(() => {
    if (reactivados.length === 0) return
    const temporizador = setTimeout(() => setReactivados([]), DURACION_REACTIVADOS_MS)
    return () => clearTimeout(temporizador)
  }, [reactivados])

  const visibles = useMemo(() => filtrarProductosCocina(productos ?? [], busqueda), [productos, busqueda])
  const cerrarConfirmacion = useCallback(() => setConfirmando(null), [])

  async function confirmar() {
    const producto = confirmando
    setEnviando(true)
    try {
      const reporte = await marcarAgotado(producto.id)
      setMensaje({
        tipo: 'exito',
        texto: `${reporte.producto_nombre} salió del menú y se avisó al operador. Reportado a las ${horaExacta(reporte.fecha_hora)}`,
      })
    } catch (error) {
      setMensaje({ tipo: 'error', texto: interpretarError(error).general })
    } finally {
      setEnviando(false)
      setConfirmando(null)
      setRecarga((numero) => numero + 1)
    }
  }

  return (
    <div className="flex flex-col gap-4">
      <header>
        <h1 className="text-2xl font-bold">Productos de la sede</h1>
        <p className="text-texto-suave">
          Si se acabó un insumo, marca el producto como agotado: sale del menú de tu sede y el operador recibe el
          aviso. El operador lo vuelve a habilitar cuando haya existencias. La lista se actualiza sola cada{' '}
          {INTERVALO_MS / 1000} segundos.
        </p>
      </header>

      {reactivados.length > 0 && (
        <Alerta
          tipo="exito"
          titulo={
            reactivados.length === 1
              ? `${reactivados[0]} vuelve a estar disponible.`
              : `Vuelven a estar disponibles: ${reactivados.join(', ')}.`
          }
        >
          <button type="button" onClick={() => setReactivados([])} className="mt-1 text-sm font-medium underline">
            Entendido
          </button>
        </Alerta>
      )}

      <CampoTexto
        etiqueta="Buscar producto"
        tipo="search"
        value={busqueda}
        onChange={(evento) => setBusqueda(evento.target.value)}
        placeholder="Ej: hamburguesa"
        className="max-w-md"
      />

      {mensaje && <Alerta tipo={mensaje.tipo} titulo={mensaje.texto} />}
      {errorCarga && <Alerta tipo="error" titulo={errorCarga} />}
      {!productos && !errorCarga && <p className="text-texto-suave">Cargando productos…</p>}

      {productos && visibles.length === 0 && (
        <p className="text-texto-suave">{busqueda ? 'Ningún producto coincide con la búsqueda.' : 'No hay productos.'}</p>
      )}

      {visibles.length > 0 && (
        <ul className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {visibles.map((producto) => (
            <li
              key={producto.id}
              className="flex flex-col justify-between gap-3 rounded-xl border border-borde bg-superficie p-4"
            >
              <div>
                <p className="font-bold">{producto.nombre}</p>
                <p className="text-sm text-texto-suave">{producto.categoria}</p>
                <span
                  className={`mt-2 inline-block rounded-full border px-2 py-0.5 text-xs font-medium ${
                    producto.disponible ? 'border-exito text-exito' : 'border-error text-error'
                  }`}
                >
                  {producto.disponible ? '● Disponible' : '✕ No disponible'}
                </span>
              </div>
              {producto.disponible && (
                <Boton
                  variante="peligro"
                  onClick={() => setConfirmando(producto)}
                  aria-label={`Marcar agotado: ${producto.nombre}`}
                >
                  Marcar agotado
                </Boton>
              )}
            </li>
          ))}
        </ul>
      )}

      {confirmando && (
        <Modal
          titulo="¿Marcar como agotado?"
          alCerrar={cerrarConfirmacion}
          acciones={
            <>
              <Boton variante="secundario" onClick={cerrarConfirmacion} disabled={enviando}>
                Cancelar
              </Boton>
              <Boton variante="peligro" onClick={confirmar} cargando={enviando}>
                Sí, marcar agotado
              </Boton>
            </>
          }
        >
          <p>
            <strong>{confirmando.nombre}</strong> saldrá de inmediato del menú de tu sede y los clientes no podrán
            agregarlo al carrito.
          </p>
        </Modal>
      )}
    </div>
  )
}
