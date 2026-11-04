import { useEffect, useState } from 'react'
import { eliminarDireccion, listarDirecciones } from '../../api/direcciones.js'
import { interpretarError } from '../../api/errores.js'
import FormularioDireccion from '../../components/direcciones/FormularioDireccion.jsx'
import TarjetaDireccion from '../../components/direcciones/TarjetaDireccion.jsx'
import Alerta from '../../components/ui/Alerta.jsx'
import Tarjeta from '../../components/ui/Tarjeta.jsx'

// HU-06 · Direcciones de entrega georreferenciadas (vista del cliente).
export default function Direcciones() {
  const [direcciones, setDirecciones] = useState([])
  const [cargando, setCargando] = useState(true)
  const [errorCarga, setErrorCarga] = useState(null)
  const [recarga, setRecarga] = useState(0)
  const [editando, setEditando] = useState(null)
  // Cambia después de crear para dejar el formulario de "nueva" en blanco.
  const [formulario, setFormulario] = useState(0)
  const [mensaje, setMensaje] = useState(null)

  useEffect(() => {
    let vigente = true
    listarDirecciones()
      .then((datos) => {
        if (!vigente) return
        setDirecciones(datos)
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
  }, [recarga])

  function recargar() {
    setRecarga((valor) => valor + 1)
  }

  function alGuardar(direccion, fueEdicion) {
    setMensaje({
      tipo: 'exito',
      texto: fueEdicion
        ? `Se guardaron los cambios de "${direccion.alias}". Los pedidos anteriores conservan su dirección.`
        : `Se guardó la dirección "${direccion.alias}".`,
    })
    setEditando(null)
    setFormulario((valor) => valor + 1)
    recargar()
  }

  async function eliminar(direccion) {
    const confirmado = window.confirm(
      `¿Eliminar la dirección "${direccion.alias}"? Los pedidos que ya hiciste a esta dirección no cambian.`,
    )
    if (!confirmado) return
    try {
      await eliminarDireccion(direccion.id)
      if (editando?.id === direccion.id) setEditando(null)
      setMensaje({ tipo: 'exito', texto: `Se eliminó la dirección "${direccion.alias}".` })
      recargar()
    } catch (err) {
      setMensaje({ tipo: 'error', texto: interpretarError(err).general })
    }
  }

  return (
    <div className="flex flex-col gap-6">
      <header>
        <h1 className="text-2xl font-bold">Mis direcciones</h1>
        <p className="text-texto-suave">
          Guarda los lugares donde recibes tus pedidos y ubícalos en el mapa para que el repartidor llegue sin
          problema.
        </p>
      </header>

      {mensaje && <Alerta tipo={mensaje.tipo} titulo={mensaje.texto} />}
      {errorCarga && <Alerta tipo="error" titulo={errorCarga} />}

      <div className="grid gap-6 lg:grid-cols-[minmax(0,3fr)_minmax(0,2fr)]">
        <Tarjeta>
          <FormularioDireccion
            key={editando ? `editar-${editando.id}` : `nueva-${formulario}`}
            direccion={editando}
            alGuardar={alGuardar}
            alCancelar={() => setEditando(null)}
          />
        </Tarjeta>

        <Tarjeta titulo="Direcciones guardadas">
          {cargando ? (
            <p className="text-texto-suave">Cargando direcciones…</p>
          ) : direcciones.length === 0 ? (
            <p className="text-texto-suave">Todavía no tienes direcciones guardadas.</p>
          ) : (
            <ul className="flex flex-col gap-2">
              {direcciones.map((direccion) => (
                <TarjetaDireccion
                  key={direccion.id}
                  direccion={direccion}
                  alEditar={() => setEditando(direccion)}
                  alEliminar={() => eliminar(direccion)}
                />
              ))}
            </ul>
          )}
        </Tarjeta>
      </div>
    </div>
  )
}
