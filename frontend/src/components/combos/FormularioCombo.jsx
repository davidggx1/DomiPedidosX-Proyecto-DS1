import { useEffect, useId, useState } from 'react'
import { actualizarCombo, crearCombo } from '../../api/combos.js'
import { interpretarError } from '../../api/errores.js'
import { listarSedes } from '../../api/sedes.js'
import { ROLES } from '../../auth/roles.js'
import { useAuth } from '../../auth/useAuth.js'
import { formatearPrecio } from '../../utils/formato.js'
import {
  ahorroCombo,
  armarCuerpoCombo,
  datosInicialesCombo,
  sumaIndividual,
  validarCombo,
} from '../../utils/combos.js'
import Alerta from '../ui/Alerta.jsx'
import Boton from '../ui/Boton.jsx'
import CampoTexto from '../ui/CampoTexto.jsx'
import Selector from '../ui/Selector.jsx'

// HU-85 · Crear o editar un combo. Sin `combo` es uno nuevo.
// `productos` es la lista del menú (activos). alGuardar(combo, fueEdicion) se llama al guardar.
export default function FormularioCombo({ combo = null, productos, alGuardar, alCancelar }) {
  const editando = Boolean(combo)
  const [datos, setDatos] = useState(() => datosInicialesCombo(combo))
  const [errores, setErrores] = useState({})
  const [errorGeneral, setErrorGeneral] = useState(null)
  const [guardando, setGuardando] = useState(false)
  const idDescripcion = useId()

  // El administrador elige la sede al crear; el operador siempre crea en la suya.
  const { usuario } = useAuth()
  const debeElegirSede = !editando && usuario?.rol === ROLES.ADMINISTRADOR
  const [sedes, setSedes] = useState([])
  const [sedeId, setSedeId] = useState('')

  useEffect(() => {
    if (!debeElegirSede) return undefined
    let activo = true
    listarSedes()
      .then((lista) => {
        if (activo) setSedes(lista.filter((sede) => sede.activa))
      })
      .catch(() => {})
    return () => {
      activo = false
    }
  }, [debeElegirSede])

  function quitarError(nombre) {
    setErrores((actuales) => {
      if (!actuales[nombre]) return actuales
      const resto = { ...actuales }
      delete resto[nombre]
      return resto
    })
  }

  function cambiar(evento) {
    const { name, value } = evento.target
    setDatos((actuales) => ({ ...actuales, [name]: value }))
    quitarError(name)
  }

  function marcarProducto(producto, marcado) {
    setDatos((actuales) => {
      const lineas = { ...actuales.lineas }
      if (marcado) lineas[producto.id] = lineas[producto.id] ?? '1'
      else delete lineas[producto.id]
      return { ...actuales, lineas }
    })
    quitarError('productos')
    quitarError('precio')
  }

  function cambiarCantidad(producto, valor) {
    setDatos((actuales) => ({
      ...actuales,
      lineas: { ...actuales.lineas, [producto.id]: valor.replace(/\D/g, '') },
    }))
    quitarError('productos')
  }

  const suma = sumaIndividual(datos.lineas, productos)
  const ahorro = ahorroCombo(datos.precio, suma)

  async function enviar(evento) {
    evento.preventDefault()
    setErrorGeneral(null)

    const erroresLocales = validarCombo(datos, productos)
    if (debeElegirSede && !sedeId) erroresLocales.sede = 'Elige la sede del combo.'
    setErrores(erroresLocales)
    if (Object.keys(erroresLocales).length > 0) {
      setErrorGeneral('Revisa los campos marcados.')
      return
    }

    setGuardando(true)
    try {
      const cuerpo = armarCuerpoCombo(datos)
      if (debeElegirSede) cuerpo.sede = Number(sedeId)
      const guardado = editando
        ? await actualizarCombo(combo.id, cuerpo)
        : await crearCombo(cuerpo)
      if (!editando) {
        setDatos(datosInicialesCombo(null))
        setSedeId('')
      }
      alGuardar(guardado, editando)
    } catch (error) {
      const { general, campos } = interpretarError(error)
      setErrores(campos)
      setErrorGeneral(campos.sede ?? campos.non_field_errors ?? general)
    } finally {
      setGuardando(false)
    }
  }

  return (
    <form noValidate onSubmit={enviar} className="flex flex-col gap-3">
      <h2 className="text-lg font-bold">{editando ? 'Editar combo' : 'Nuevo combo'}</h2>

      {errorGeneral && <Alerta tipo="error" titulo={errorGeneral} />}

      {debeElegirSede && (
        <Selector
          etiqueta="Sede"
          opciones={[
            { valor: '', etiqueta: 'Elige una sede…' },
            ...sedes.map((sede) => ({ valor: String(sede.id), etiqueta: sede.nombre })),
          ]}
          requerido
          value={sedeId}
          onChange={(evento) => {
            setSedeId(evento.target.value)
            quitarError('sede')
          }}
          error={errores.sede}
        />
      )}

      <CampoTexto
        etiqueta="Nombre"
        name="nombre"
        maxLength={100}
        requerido
        value={datos.nombre}
        onChange={cambiar}
        error={errores.nombre}
      />

      <div className="flex flex-col gap-1">
        <label htmlFor={idDescripcion} className="text-sm font-medium">
          Descripción
        </label>
        <textarea
          id={idDescripcion}
          name="descripcion"
          rows={2}
          value={datos.descripcion}
          onChange={cambiar}
          className="w-full rounded-lg border border-borde bg-fondo p-2.5 text-texto"
        />
      </div>

      <fieldset className="flex flex-col gap-2">
        <legend className="text-sm font-medium">Productos del combo *</legend>
        {productos.length === 0 ? (
          <p className="text-sm text-texto-suave">No hay productos activos en el menú.</p>
        ) : (
          <ul className="flex max-h-56 flex-col gap-1 overflow-y-auto rounded-lg border border-borde bg-fondo p-2">
            {productos.map((producto) => {
              const marcado = datos.lineas[producto.id] !== undefined
              return (
                <li key={producto.id} className="flex items-center justify-between gap-2">
                  <label className="flex min-w-0 flex-1 items-center gap-2 text-sm">
                    <input
                      type="checkbox"
                      checked={marcado}
                      onChange={(evento) => marcarProducto(producto, evento.target.checked)}
                    />
                    <span className="truncate">{producto.nombre}</span>
                    <span className="text-texto-suave">{formatearPrecio(producto.precio_base)}</span>
                  </label>
                  {marcado && (
                    <input
                      type="text"
                      inputMode="numeric"
                      aria-label={`Cantidad de ${producto.nombre}`}
                      value={datos.lineas[producto.id]}
                      onChange={(evento) => cambiarCantidad(producto, evento.target.value)}
                      className="w-14 rounded-lg border border-borde bg-superficie p-1 text-center text-texto"
                    />
                  )}
                </li>
              )
            })}
          </ul>
        )}
        {errores.productos && <p className="text-sm text-error">{errores.productos}</p>}
      </fieldset>

      <CampoTexto
        etiqueta="Precio del combo ($)"
        name="precio"
        inputMode="decimal"
        requerido
        ayuda={
          suma > 0
            ? `Total individual: ${formatearPrecio(suma)}. El precio debe ser menor.`
            : 'Debe ser menor que el total individual de los productos.'
        }
        value={datos.precio}
        onChange={cambiar}
        error={errores.precio}
      />
      {ahorro !== null && ahorro > 0 && (
        <p className="text-sm text-exito">El cliente ahorra {formatearPrecio(ahorro)}.</p>
      )}

      <div className="grid gap-3 sm:grid-cols-2">
        <CampoTexto
          etiqueta="Vigente desde"
          name="fecha_inicio"
          type="date"
          requerido
          value={datos.fecha_inicio}
          onChange={cambiar}
          error={errores.fecha_inicio}
        />
        <CampoTexto
          etiqueta="Vigente hasta"
          name="fecha_vencimiento"
          type="date"
          min={datos.fecha_inicio || undefined}
          requerido
          value={datos.fecha_vencimiento}
          onChange={cambiar}
          error={errores.fecha_vencimiento}
        />
      </div>

      <CampoTexto
        etiqueta="Cupo diario de usos"
        name="cupo_max_diario"
        inputMode="numeric"
        ayuda="Máximo de unidades del combo por día. Vacío = sin límite. Se reinicia a las 00:00."
        value={datos.cupo_max_diario}
        onChange={cambiar}
        error={errores.cupo_max_diario}
      />

      <p className="text-sm text-texto-suave">
        Los cambios aplican a las compras que se hagan después de guardar. Los pedidos anteriores no cambian.
      </p>

      <div className="flex flex-wrap gap-2">
        <Boton tipo="submit" cargando={guardando}>
          {editando ? 'Guardar cambios' : 'Crear combo'}
        </Boton>
        {editando && (
          <Boton variante="secundario" onClick={alCancelar}>
            Cancelar
          </Boton>
        )}
      </div>
    </form>
  )
}