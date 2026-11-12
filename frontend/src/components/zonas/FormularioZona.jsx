import Boton from '../ui/Boton.jsx'
import CampoTexto from '../ui/CampoTexto.jsx'
import Casilla from '../ui/Casilla.jsx'
import { formularioConfigurado } from '../../utils/zonas.js'

// Datos de la zona que no dependen del mapa. Los errores llegan por campo
// (interpretarError -> campos). Tarifa y tiempo son opcionales, pero sin ellos
// la zona queda desactivada (HU-56).
export default function FormularioZona({
  valores,
  alCambiar,
  errores = {},
  resumenForma,
  guardando,
  alGuardar,
  alCancelar,
}) {
  const configurada = formularioConfigurado(valores)

  const poner = (campo) => (e) => {
    const siguiente = { ...valores, [campo]: e.target.value }
    // Sin tarifa y tiempo la zona no puede estar activa.
    if (!formularioConfigurado(siguiente)) siguiente.activo = false
    alCambiar(siguiente)
  }

  return (
    <form onSubmit={alGuardar} className="flex flex-col gap-4">
      <CampoTexto
        etiqueta="Nombre de la zona"
        value={valores.nombre}
        onChange={(e) => alCambiar({ ...valores, nombre: e.target.value })}
        error={errores.nombre}
        requerido
      />

      <div className="rounded-lg border border-borde bg-fondo px-3 py-2 text-sm">
        <p className="font-medium">Forma en el mapa</p>
        <p className={errores.radio || errores.poligono_vertices ? 'text-error' : 'text-texto-suave'}>
          {resumenForma ??
            'Dibuja un círculo o un polígono con las herramientas del mapa.'}
        </p>
        {(errores.radio || errores.poligono_vertices) && (
          <p className="text-error">{errores.radio ?? errores.poligono_vertices}</p>
        )}
      </div>

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
        <CampoTexto
          etiqueta="Tarifa de domicilio ($)"
          tipo="number"
          min="0"
          step="100"
          value={valores.tarifa_domicilio}
          onChange={poner('tarifa_domicilio')}
          error={errores.tarifa_domicilio}
          ayuda="0 = domicilio gratis"
        />
        <CampoTexto
          etiqueta="Tiempo estimado (min)"
          tipo="number"
          min="1"
          step="1"
          value={valores.tiempo_estimado}
          onChange={poner('tiempo_estimado')}
          error={errores.tiempo_estimado}
        />
        <CampoTexto
          etiqueta="Pedido mínimo ($)"
          tipo="number"
          min="0"
          step="100"
          value={valores.pedido_minimo}
          onChange={poner('pedido_minimo')}
          error={errores.pedido_minimo}
          ayuda="0 = sin pedido mínimo"
          requerido
        />
      </div>

      <Casilla
        etiqueta="Zona activa"
        descripcion={
          configurada
            ? 'Solo las zonas activas reciben pedidos y se comparan para evitar traslapes'
            : 'Define tarifa y tiempo estimado para poder activarla'
        }
        checked={valores.activo}
        onChange={(e) => {
          if (e.target.checked && !configurada) return
          alCambiar({ ...valores, activo: e.target.checked })
        }}
      />

      <div className="flex justify-end gap-3">
        <Boton variante="secundario" onClick={alCancelar} disabled={guardando}>
          Cancelar
        </Boton>
        <Boton tipo="submit" cargando={guardando}>
          Guardar zona
        </Boton>
      </div>
    </form>
  )
}