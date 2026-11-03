import { useState } from 'react'
import { actualizarInsumo, crearInsumo } from '../../api/menu.js'
import { interpretarError } from '../../api/errores.js'
import { UNIDADES } from '../../utils/unidades.js'
import Alerta from '../ui/Alerta.jsx'
import Boton from '../ui/Boton.jsx'
import CampoTexto from '../ui/CampoTexto.jsx'
import Selector from '../ui/Selector.jsx'

const VACIO = { nombre: '', unidad_medida: '' }

function valoresIniciales(insumo) {
  if (!insumo) return VACIO
  return { nombre: insumo.nombre, unidad_medida: insumo.unidad_medida }
}

// Mismas reglas que el backend, para avisar antes de enviar.
function validar(valores) {
  const errores = {}
  if (!valores.nombre.trim()) {
    errores.nombre = 'El nombre del ingrediente es obligatorio.'
  }
  if (!valores.unidad_medida) {
    errores.unidad_medida = 'Selecciona la unidad de medida.'
  }
  return errores
}

// Formulario para registrar o editar un ingrediente del catálogo (HU-77).
// Si recibe `insumo`, edita; si no, crea uno nuevo.
// El padre debe darle una `key` distinta al cambiar de ingrediente para reiniciarlo.
export default function FormularioInsumo({ insumo, alGuardar, alCancelar }) {
  const esEdicion = Boolean(insumo)
  const [valores, setValores] = useState(() => valoresIniciales(insumo))
  const [errores, setErrores] = useState({})
  const [errorGeneral, setErrorGeneral] = useState(null)
  const [guardando, setGuardando] = useState(false)

  function cambiar(evento) {
    const { name, value } = evento.target
    setValores((actuales) => ({ ...actuales, [name]: value }))
  }

  async function enviar(evento) {
    evento.preventDefault()
    const nuevosErrores = validar(valores)
    setErrores(nuevosErrores)
    setErrorGeneral(null)
    if (Object.keys(nuevosErrores).length > 0) return

    const datos = { nombre: valores.nombre.trim(), unidad_medida: valores.unidad_medida }

    setGuardando(true)
    try {
      const guardado = esEdicion
        ? await actualizarInsumo(insumo.id, datos)
        : await crearInsumo(datos)
      if (!esEdicion) setValores(VACIO)
      alGuardar(guardado, esEdicion)
    } catch (error) {
      const { general, campos } = interpretarError(error)
      setErrorGeneral(general)
      setErrores(campos)
    } finally {
      setGuardando(false)
    }
  }

  return (
    <form noValidate onSubmit={enviar} className="flex flex-col gap-4">
      <h2 className="text-lg font-bold">
        {esEdicion ? `Editar "${insumo.nombre}"` : 'Nuevo ingrediente'}
      </h2>

      {errorGeneral && <Alerta tipo="error" titulo={errorGeneral} />}

      <CampoTexto
        etiqueta="Nombre"
        name="nombre"
        value={valores.nombre}
        onChange={cambiar}
        error={errores.nombre}
        placeholder="Ej.: Cebolla"
        maxLength={100}
        requerido
      />
      <Selector
        etiqueta="Unidad de medida"
        name="unidad_medida"
        opciones={UNIDADES}
        value={valores.unidad_medida}
        onChange={cambiar}
        error={errores.unidad_medida}
        textoVacio="Selecciona una unidad"
        requerido
      />

      <div className="flex flex-wrap gap-3">
        <Boton tipo="submit" cargando={guardando}>
          {esEdicion ? 'Guardar cambios' : 'Registrar ingrediente'}
        </Boton>
        {esEdicion && (
          <Boton variante="secundario" onClick={alCancelar}>
            Cancelar
          </Boton>
        )}
      </div>
    </form>
  )
}
