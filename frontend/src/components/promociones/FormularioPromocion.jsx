import { useId, useState } from 'react'
import { actualizarPromocion, crearPromocion } from '../../api/promociones.js'
import { interpretarError } from '../../api/errores.js'
import Alerta from '../ui/Alerta.jsx'
import Boton from '../ui/Boton.jsx'
import CampoTexto from '../ui/CampoTexto.jsx'
import Selector from '../ui/Selector.jsx'
import {
  TIPOS_DESCUENTO,
  armarCuerpoPromocion,
  datosIniciales,
  etiquetaValor,
  validarPromocion,
} from '../../utils/promociones.js'

// HU-84 · Crear o editar una promoción. Sin `promocion` es una nueva.
// alGuardar(promocion, fueEdicion) se llama cuando el servidor la acepta.
export default function FormularioPromocion({ promocion = null, alGuardar, alCancelar }) {
  const editando = Boolean(promocion)
  const [datos, setDatos] = useState(() => datosIniciales(promocion))
  const [errores, setErrores] = useState({})
  const [errorGeneral, setErrorGeneral] = useState(null)
  const [guardando, setGuardando] = useState(false)
  const idCondiciones = useId()
  const idDescripcion = useId()

  function cambiar(evento) {
    const { name, value } = evento.target
    setDatos((actuales) => ({ ...actuales, [name]: value }))
    // Al corregir un campo, se quita su error.
    setErrores((actuales) => {
      if (!actuales[name]) return actuales
      const resto = { ...actuales }
      delete resto[name]
      return resto
    })
  }

  async function enviar(evento) {
    evento.preventDefault()
    setErrorGeneral(null)

    const erroresLocales = validarPromocion(datos)
    setErrores(erroresLocales)
    if (Object.keys(erroresLocales).length > 0) {
      setErrorGeneral('Revisa los campos marcados.')
      return
    }

    setGuardando(true)
    try {
      const cuerpo = armarCuerpoPromocion(datos)
      const guardada = editando
        ? await actualizarPromocion(promocion.id, cuerpo)
        : await crearPromocion(cuerpo)
      if (!editando) setDatos(datosIniciales(null))
      alGuardar(guardada, editando)
    } catch (error) {
      const { general, campos } = interpretarError(error)
      setErrores(campos)
      // El error de la sede no tiene campo en este formulario: se muestra arriba.
      setErrorGeneral(campos.sede ?? general)
    } finally {
      setGuardando(false)
    }
  }

  return (
    <form noValidate onSubmit={enviar} className="flex flex-col gap-3">
      <h2 className="text-lg font-bold">{editando ? 'Editar promoción' : 'Nueva promoción'}</h2>

      {errorGeneral && <Alerta tipo="error" titulo={errorGeneral} />}

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

      <div className="grid gap-3 sm:grid-cols-2">
        <Selector
          etiqueta="Tipo de descuento"
          name="tipo_descuento"
          opciones={TIPOS_DESCUENTO}
          requerido
          value={datos.tipo_descuento}
          onChange={cambiar}
          error={errores.tipo_descuento}
        />
        <CampoTexto
          etiqueta={etiquetaValor(datos.tipo_descuento)}
          name="valor"
          inputMode="decimal"
          requerido
          ayuda={datos.tipo_descuento === 'porcentaje' ? 'Entre 0 y 100.' : 'En pesos, mayor que 0.'}
          value={datos.valor}
          onChange={cambiar}
          error={errores.valor}
        />
      </div>

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
          name="fecha_fin"
          type="date"
          min={datos.fecha_inicio || undefined}
          requerido
          value={datos.fecha_fin}
          onChange={cambiar}
          error={errores.fecha_fin}
        />
      </div>

      <div className="flex flex-col gap-1">
        <label htmlFor={idCondiciones} className="text-sm font-medium">
          Condiciones
        </label>
        <textarea
          id={idCondiciones}
          name="condiciones"
          rows={3}
          placeholder="Ej: Solo domicilios, pedido mínimo de $30.000…"
          value={datos.condiciones}
          onChange={cambiar}
          className="w-full rounded-lg border border-borde bg-fondo p-2.5 text-texto placeholder:text-texto-suave"
        />
        {errores.condiciones && <p className="text-sm text-error">{errores.condiciones}</p>}
      </div>

      <p className="text-sm text-texto-suave">
        Los cambios aplican a las compras que se hagan después de guardar. Las compras anteriores no cambian.
      </p>

      <div className="flex flex-wrap gap-2">
        <Boton tipo="submit" cargando={guardando}>
          {editando ? 'Guardar cambios' : 'Crear promoción'}
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