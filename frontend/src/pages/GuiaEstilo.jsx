import { useState } from 'react'
import Alerta from '../components/ui/Alerta.jsx'
import Boton from '../components/ui/Boton.jsx'
import CampoTexto from '../components/ui/CampoTexto.jsx'
import Casilla from '../components/ui/Casilla.jsx'
import Selector from '../components/ui/Selector.jsx'
import Tarjeta from '../components/ui/Tarjeta.jsx'
import TarjetaProducto from '../components/menu/TarjetaProducto.jsx'

// Catálogo de los componentes base (SCRUM-20).
// Sirve de referencia al equipo para construir pantallas con el mismo estilo.
const SEDES_EJEMPLO = [
  { valor: '1', etiqueta: 'Sede Centro' },
  { valor: '2', etiqueta: 'Sede Sur' },
]

const PRODUCTOS_EJEMPLO = [
  { id: 1, nombre: 'Hamburguesa clásica', precio: '18000', disponible: true },
  { id: 2, nombre: 'Limonada natural', precio: '6000', disponible: false },
]

const VALORES_INICIALES = { nombre: '', correo: '', sede: '', excluible: false }
const FORMATO_CORREO = /^[^\s@]+@[^\s@]+\.[^\s@]+$/

function validar(valores) {
  const errores = {}
  if (!valores.nombre.trim()) {
    errores.nombre = 'Escribe el nombre.'
  }
  if (!valores.correo.trim()) {
    errores.correo = 'Escribe el correo.'
  } else if (!FORMATO_CORREO.test(valores.correo)) {
    errores.correo = 'El correo no tiene un formato válido. Ejemplo: ana@correo.com'
  }
  if (!valores.sede) {
    errores.sede = 'Selecciona una sede.'
  }
  return errores
}

export default function GuiaEstilo() {
  const [valores, setValores] = useState(VALORES_INICIALES)
  const [errores, setErrores] = useState({})
  const [enviado, setEnviado] = useState(false)

  function cambiar(evento) {
    const { name, value, type, checked } = evento.target
    setValores((actuales) => ({ ...actuales, [name]: type === 'checkbox' ? checked : value }))
  }

  function enviar(evento) {
    evento.preventDefault()
    const nuevosErrores = validar(valores)
    setErrores(nuevosErrores)
    setEnviado(Object.keys(nuevosErrores).length === 0)
  }

  function limpiar() {
    setValores(VALORES_INICIALES)
    setErrores({})
    setEnviado(false)
  }

  const hayErrores = Object.keys(errores).length > 0

  return (
    <div className="flex flex-col gap-8">
      <header>
        <h1 className="text-2xl font-bold">Guía de estilo</h1>
        <p className="text-texto-suave">Componentes base de la interfaz de DomiPedidosX.</p>
      </header>

      <Tarjeta titulo="Botones">
        <div className="flex flex-wrap gap-3">
          <Boton>Primario</Boton>
          <Boton variante="secundario">Secundario</Boton>
          <Boton variante="peligro">Cancelar pedido</Boton>
          <Boton variante="fantasma">Fantasma</Boton>
          <Boton cargando>Guardar</Boton>
          <Boton disabled>Deshabilitado</Boton>
        </div>
      </Tarjeta>

      <Tarjeta titulo="Mensajes">
        <div className="flex flex-col gap-3">
          <Alerta tipo="exito" titulo="Pedido confirmado.">Tu pedido #1042 fue recibido.</Alerta>
          <Alerta tipo="error" titulo="No se pudo guardar.">Revisa los campos marcados.</Alerta>
          <Alerta tipo="aviso" titulo="Stock bajo el mínimo.">Hamburguesa clásica: quedan 4.</Alerta>
          <Alerta tipo="info">La sede abre a las 11:00 a. m.</Alerta>
        </div>
      </Tarjeta>

      <Tarjeta titulo="Formulario con validación">
        <form noValidate onSubmit={enviar} className="flex max-w-lg flex-col gap-4">
          {hayErrores && (
            <Alerta tipo="error" titulo="Revisa los campos marcados." />
          )}
          {enviado && (
            <Alerta tipo="exito" titulo="Formulario válido." />
          )}

          <CampoTexto
            etiqueta="Nombre"
            name="nombre"
            value={valores.nombre}
            onChange={cambiar}
            error={errores.nombre}
            requerido
            autoComplete="name"
          />
          <CampoTexto
            etiqueta="Correo electrónico"
            name="correo"
            type="email"
            value={valores.correo}
            onChange={cambiar}
            error={errores.correo}
            ayuda="Lo usamos para enviarte la confirmación del pedido."
            requerido
            autoComplete="email"
          />
          <Selector
            etiqueta="Sede"
            name="sede"
            opciones={SEDES_EJEMPLO}
            value={valores.sede}
            onChange={cambiar}
            error={errores.sede}
            requerido
          />
          <Casilla
            etiqueta="Ingrediente excluible"
            descripcion="El cliente podrá pedir el producto sin este ingrediente."
            name="excluible"
            checked={valores.excluible}
            onChange={cambiar}
          />

          <div className="flex flex-wrap gap-3">
            <Boton tipo="submit">Enviar</Boton>
            <Boton variante="secundario" onClick={limpiar}>
              Limpiar
            </Boton>
          </div>
        </form>
      </Tarjeta>

      <section>
        <h2 className="mb-3 text-lg font-bold">Tarjetas de producto</h2>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {PRODUCTOS_EJEMPLO.map((producto) => (
            <TarjetaProducto key={producto.id} producto={producto} />
          ))}
        </div>
      </section>
    </div>
  )
}
