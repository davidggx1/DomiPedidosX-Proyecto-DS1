import Boton from '../ui/Boton.jsx'
import CampoTexto from '../ui/CampoTexto.jsx'
import Casilla from '../ui/Casilla.jsx'

// Datos de la zona que no dependen del mapa. Los errores llegan por campo
// (interpretarError -> campos).
export default function FormularioZona({
  valores,
  alCambiar,
  errores = {},
  resumenForma,
  guardando,
  alGuardar,
  alCancelar,
}) {
  const poner = (campo) => (e) => alCambiar({ ...valores, [campo]: e.target.value })

  return (
    <form onSubmit={alGuardar} className="flex flex-col gap-4">
      <CampoTexto
        etiqueta="Nombre de la zona"
        value={valores.nombre}
        onChange={poner('nombre')}
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
          requerido
        />
        <CampoTexto
          etiqueta="Tiempo estimado (min)"
          tipo="number"
          min="1"
          step="1"
          value={valores.tiempo_estimado}
          onChange={poner('tiempo_estimado')}
          error={errores.tiempo_estimado}
          requerido
        />
        <CampoTexto
          etiqueta="Pedido mínimo ($)"
          tipo="number"
          min="0"
          step="100"
          value={valores.pedido_minimo}
          onChange={poner('pedido_minimo')}
          error={errores.pedido_minimo}
          requerido
        />
      </div>

      <Casilla
        etiqueta="Zona activa"
        descripcion="Solo las zonas activas reciben pedidos y se comparan para evitar traslapes"
        checked={valores.activo}
        onChange={(e) => alCambiar({ ...valores, activo: e.target.checked })}
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