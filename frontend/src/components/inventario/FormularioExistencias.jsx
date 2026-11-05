import { useState } from 'react'
import { ajustarExistencias, registrarExistencias } from '../../api/inventario.js'
import { interpretarError } from '../../api/errores.js'
import { TIPOS_EXISTENCIAS } from '../../utils/existencias.js'
import { abreviaturaUnidad } from '../../utils/unidades.js'
import Alerta from '../ui/Alerta.jsx'
import Boton from '../ui/Boton.jsx'
import CampoTexto from '../ui/CampoTexto.jsx'
import Selector from '../ui/Selector.jsx'

function valoresIniciales(registro) {
  if (!registro) return { item: '', stock_actual: '', stock_minimo: '0' }
  return {
    item: '',
    stock_actual: String(Number(registro.stock_actual)),
    stock_minimo: String(Number(registro.stock_minimo)),
  }
}

// Same rules as the backend, to warn before sending
function validarNumero(texto, { etiqueta, entero, obligatorio }) {
  const valor = texto.trim()
  if (valor === '') return obligatorio ? `${etiqueta} es obligatorio.` : null
  const numero = Number(valor)
  if (Number.isNaN(numero)) return `${etiqueta} debe ser un número válido.`
  if (numero < 0) return `${etiqueta} no puede ser negativo.`
  if (entero && !Number.isInteger(numero)) return `${etiqueta} debe ser un número entero.`
  return null
}

// Form to register or adjust the stock of a product or an ingredient in the sede (HU-14)
// With `registro` it adjusts that record, without it creates a new one
// The parent should change the `key` when `registro` changes to reset the form
export default function FormularioExistencias({
  tipo,
  registro,
  opcionesItem,
  alGuardar,
  alCancelar,
}) {
  const config = TIPOS_EXISTENCIAS[tipo]
  const esEdicion = Boolean(registro)
  const [valores, setValores] = useState(() => valoresIniciales(registro))
  const [errores, setErrores] = useState({})
  const [errorGeneral, setErrorGeneral] = useState(null)
  const [guardando, setGuardando] = useState(false)

  const itemElegido = opcionesItem.find((opcion) => opcion.valor === valores.item)
  const unidad = esEdicion ? registro.unidad_medida : itemElegido?.unidad
  const ayudaUnidad = tipo === 'insumos' && unidad ? `En ${abreviaturaUnidad(unidad)}` : undefined

  function cambiar(evento) {
    const { name, value } = evento.target
    setValores((actuales) => ({ ...actuales, [name]: value }))
  }

  async function enviar(evento) {
    evento.preventDefault()
    const nuevosErrores = {}
    if (!esEdicion && !valores.item) {
      nuevosErrores.item = `Selecciona el ${config.etiquetaItem.toLowerCase()}.`
    }
    const errorActual = validarNumero(valores.stock_actual, {
      etiqueta: 'El stock actual',
      entero: config.entero,
      obligatorio: true,
    })
    if (errorActual) nuevosErrores.stock_actual = errorActual
    const errorMinimo = validarNumero(valores.stock_minimo, {
      etiqueta: 'El stock mínimo',
      entero: config.entero,
      obligatorio: false,
    })
    if (errorMinimo) nuevosErrores.stock_minimo = errorMinimo

    setErrores(nuevosErrores)
    setErrorGeneral(null)
    if (Object.keys(nuevosErrores).length > 0) return

    // decimals travel as text so no precision is lost
    const convertir = (texto) => (config.entero ? Number(texto) : texto.trim())
    const datos = {
      stock_actual: convertir(valores.stock_actual),
      stock_minimo: valores.stock_minimo.trim() === '' ? 0 : convertir(valores.stock_minimo),
    }

    setGuardando(true)
    try {
      const guardado = esEdicion
        ? await ajustarExistencias(tipo, registro.id, datos)
        : await registrarExistencias(tipo, { ...datos, [config.campoItem]: Number(valores.item) })
      if (!esEdicion) setValores(valoresIniciales(null))
      alGuardar(guardado, esEdicion)
    } catch (error) {
      const { general, campos } = interpretarError(error)
      setErrorGeneral(general)
      // the API names the item field "producto" or "insumo", the form calls it "item"
      const { [config.campoItem]: errorItem, ...otros } = campos
      setErrores(errorItem ? { ...otros, item: errorItem } : otros)
    } finally {
      setGuardando(false)
    }
  }

  return (
    <form noValidate onSubmit={enviar} className="flex flex-col gap-4">
      <h2 className="text-lg font-bold">
        {esEdicion
          ? `Ajustar "${config.nombre(registro)}"`
          : `Registrar existencias de ${config.etiquetaItem.toLowerCase()}`}
      </h2>

      {errorGeneral && <Alerta tipo="error" titulo={errorGeneral} />}

      {!esEdicion && opcionesItem.length === 0 && (
        <Alerta tipo="info">
          Todos los {config.titulo.toLowerCase()} ya tienen existencias en tu sede. Para cambiarlas,
          usa Ajustar en la lista.
        </Alerta>
      )}

      {!esEdicion && (
        <Selector
          etiqueta={config.etiquetaItem}
          name="item"
          opciones={opcionesItem}
          value={valores.item}
          onChange={cambiar}
          error={errores.item}
          textoVacio={`Selecciona un ${config.etiquetaItem.toLowerCase()}`}
          requerido
        />
      )}

      <CampoTexto
        etiqueta="Stock actual"
        name="stock_actual"
        type="number"
        inputMode={config.entero ? 'numeric' : 'decimal'}
        min="0"
        step={config.paso}
        value={valores.stock_actual}
        onChange={cambiar}
        error={errores.stock_actual}
        ayuda={ayudaUnidad}
        requerido
      />
      <CampoTexto
        etiqueta="Stock mínimo"
        name="stock_minimo"
        type="number"
        inputMode={config.entero ? 'numeric' : 'decimal'}
        min="0"
        step={config.paso}
        value={valores.stock_minimo}
        onChange={cambiar}
        error={errores.stock_minimo}
        ayuda={ayudaUnidad}
      />

      <div className="flex flex-wrap gap-3">
        <Boton tipo="submit" cargando={guardando}>
          {esEdicion ? 'Guardar ajuste' : 'Registrar existencias'}
        </Boton>
        {esEdicion && (
          <Boton variante="secundario" onClick={alCancelar} disabled={guardando}>
            Cancelar
          </Boton>
        )}
      </div>
    </form>
  )
}
