import { useState } from 'react'
import { actualizarAdicion, crearAdicion } from '../../api/menu.js'
import { interpretarError } from '../../api/errores.js'
import Alerta from '../ui/Alerta.jsx'
import Boton from '../ui/Boton.jsx'
import CampoTexto from '../ui/CampoTexto.jsx'
import Selector from '../ui/Selector.jsx'

const VACIO = { nombre: '', precio: '', insumo: '', descripcion: '' }

function valoresIniciales(adicion) {
  if (!adicion) return VACIO
  return {
    nombre: adicion.nombre,
    precio: String(Number(adicion.precio)),
    insumo: String(adicion.insumo),
    descripcion: adicion.descripcion ?? '',
  }
}

// Mismas reglas que el backend, para avisar antes de enviar.
function validar(valores) {
  const errores = {}
  if (!valores.nombre.trim()) {
    errores.nombre = 'El nombre es obligatorio.'
  }
  if (valores.precio === '') {
    errores.precio = 'El precio es obligatorio.'
  } else if (Number.isNaN(Number(valores.precio))) {
    errores.precio = 'Escribe un precio válido.'
  } else if (Number(valores.precio) < 0) {
    errores.precio = 'El precio no puede ser negativo.'
  }
  if (!valores.insumo) {
    errores.insumo = 'Selecciona el insumo que consume la adición.'
  }
  return errores
}

// Formulario para crear o editar una adición (HU-76).
// Si recibe `adicion`, edita; si no, crea una nueva.
// El padre debe darle una `key` distinta al cambiar de adición para reiniciarlo.
export default function FormularioAdicion({ adicion, insumos, alGuardar, alCancelar }) {
  const esEdicion = Boolean(adicion)
  const [valores, setValores] = useState(() => valoresIniciales(adicion))
  const [errores, setErrores] = useState({})
  const [errorGeneral, setErrorGeneral] = useState(null)
  const [guardando, setGuardando] = useState(false)

  const opcionesInsumo = insumos.map((insumo) => ({
    valor: String(insumo.id),
    etiqueta: insumo.nombre,
  }))

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

    const datos = {
      nombre: valores.nombre.trim(),
      precio: valores.precio,
      insumo: Number(valores.insumo),
      descripcion: valores.descripcion.trim(),
    }

    setGuardando(true)
    try {
      const guardada = esEdicion
        ? await actualizarAdicion(adicion.id, datos)
        : await crearAdicion(datos)
      if (!esEdicion) setValores(VACIO)
      alGuardar(guardada, esEdicion)
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
        {esEdicion ? `Editar "${adicion.nombre}"` : 'Nueva adición'}
      </h2>

      {errorGeneral && <Alerta tipo="error" titulo={errorGeneral} />}

      <CampoTexto
        etiqueta="Nombre"
        name="nombre"
        value={valores.nombre}
        onChange={cambiar}
        error={errores.nombre}
        placeholder="Ej.: Queso extra"
        maxLength={80}
        requerido
      />
      <CampoTexto
        etiqueta="Precio (COP)"
        name="precio"
        type="number"
        inputMode="decimal"
        min="0"
        step="any"
        value={valores.precio}
        onChange={cambiar}
        error={errores.precio}
        ayuda="Se suma al precio del producto cuando el cliente la elige. Puede ser 0."
        requerido
      />
      <Selector
        etiqueta="Insumo que consume"
        name="insumo"
        opciones={opcionesInsumo}
        value={valores.insumo}
        onChange={cambiar}
        error={errores.insumo}
        textoVacio="Selecciona un insumo"
        requerido
      />
      <CampoTexto
        etiqueta="Descripción"
        name="descripcion"
        value={valores.descripcion}
        onChange={cambiar}
        error={errores.descripcion}
        placeholder="Opcional"
      />

      <div className="flex flex-wrap gap-3">
        <Boton tipo="submit" cargando={guardando}>
          {esEdicion ? 'Guardar cambios' : 'Crear adición'}
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
