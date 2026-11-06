import { useEffect, useState } from 'react'
import { cambiarEstadoCuenta, listarCuentas } from '../../api/cuentas.js'
import { interpretarError } from '../../api/errores.js'
import { ETIQUETA_ROL } from '../../auth/roles.js'
import Alerta from '../../components/ui/Alerta.jsx'
import Boton from '../../components/ui/Boton.jsx'
import CampoTexto from '../../components/ui/CampoTexto.jsx'
import Selector from '../../components/ui/Selector.jsx'
import Tarjeta from '../../components/ui/Tarjeta.jsx'

const OPCIONES_TIPO = [
  { valor: 'cliente', etiqueta: 'Clientes' },
  { valor: 'personal', etiqueta: 'Personal' },
]

const OPCIONES_ESTADO = [
  { valor: 'true', etiqueta: 'Activas' },
  { valor: 'false', etiqueta: 'Desactivadas' },
]

const FILTROS_INICIALES = { tipo: '', activa: '', buscar: '' }

// HU-09 · Desactivar cuentas (vista del administrador).
// También permite reactivarlas, adelantando HU-80.
export default function Cuentas() {
  const [filtros, setFiltros] = useState(FILTROS_INICIALES)
  const [aplicados, setAplicados] = useState(FILTROS_INICIALES)
  const [cuentas, setCuentas] = useState([])
  const [cargando, setCargando] = useState(true)
  const [error, setError] = useState(null)
  const [mensaje, setMensaje] = useState(null)
  const [procesando, setProcesando] = useState(null)
  const [recarga, setRecarga] = useState(0)

  useEffect(() => {
    let vigente = true
    listarCuentas({ ...aplicados, buscar: aplicados.buscar.trim() })
      .then((datos) => {
        if (!vigente) return
        setCuentas(datos)
        setError(null)
      })
      .catch((err) => {
        if (vigente) setError(interpretarError(err).general)
      })
      .finally(() => {
        if (vigente) setCargando(false)
      })
    return () => {
      vigente = false
    }
  }, [aplicados, recarga])

  function cambiarFiltro(evento) {
    const { name, value } = evento.target
    setFiltros((actuales) => ({ ...actuales, [name]: value }))
  }

  function buscar(evento) {
    evento.preventDefault()
    setAplicados(filtros)
  }

  function limpiar() {
    setFiltros(FILTROS_INICIALES)
    setAplicados(FILTROS_INICIALES)
  }

  async function cambiarEstado(cuenta) {
    const desactivar = cuenta.activa
    const pregunta = desactivar
      ? `¿Desactivar la cuenta de ${cuenta.nombre}? No podrá iniciar sesión y, si tiene una sesión abierta, se cerrará en su siguiente acción. Sus datos y pedidos se conservan.`
      : `¿Reactivar la cuenta de ${cuenta.nombre}? Podrá volver a iniciar sesión.`
    if (!window.confirm(pregunta)) return

    setProcesando(cuenta.id)
    setMensaje(null)
    try {
      await cambiarEstadoCuenta(cuenta.id, !desactivar)
      setMensaje({
        tipo: 'exito',
        texto: desactivar
          ? `Se desactivó la cuenta de ${cuenta.nombre}.`
          : `Se reactivó la cuenta de ${cuenta.nombre}.`,
      })
      setRecarga((valor) => valor + 1)
    } catch (err) {
      const { general, campos } = interpretarError(err)
      setMensaje({ tipo: 'error', texto: campos.activa ?? general })
    } finally {
      setProcesando(null)
    }
  }

  return (
    <div className="flex flex-col gap-6">
      <header>
        <h1 className="text-2xl font-bold">Cuentas</h1>
        <p className="text-texto-suave">
          Desactiva el acceso de clientes y personal cuando ya no corresponde.
        </p>
      </header>

      {mensaje && <Alerta tipo={mensaje.tipo} titulo={mensaje.texto} />}
      {error && <Alerta tipo="error" titulo={error} />}

      <Tarjeta>
        <form
          onSubmit={buscar}
          role="search"
          className="flex flex-col gap-3 md:flex-row md:items-end"
        >
          <CampoTexto
            etiqueta="Buscar"
            name="buscar"
            value={filtros.buscar}
            onChange={cambiarFiltro}
            placeholder="Correo, nombres o apellidos"
            className="md:flex-1"
          />
          <Selector
            etiqueta="Tipo"
            name="tipo"
            opciones={OPCIONES_TIPO}
            value={filtros.tipo}
            onChange={cambiarFiltro}
            textoVacio="Todas"
            className="md:w-44"
          />
          <Selector
            etiqueta="Estado"
            name="activa"
            opciones={OPCIONES_ESTADO}
            value={filtros.activa}
            onChange={cambiarFiltro}
            textoVacio="Todas"
            className="md:w-44"
          />
          <div className="flex gap-2">
            <Boton tipo="submit">Buscar</Boton>
            <Boton variante="secundario" onClick={limpiar}>
              Limpiar
            </Boton>
          </div>
        </form>
      </Tarjeta>

      <Tarjeta titulo="Resultados">
        {cargando ? (
          <p className="text-texto-suave">Cargando cuentas…</p>
        ) : cuentas.length === 0 ? (
          <p className="text-texto-suave">No hay cuentas que coincidan con la búsqueda.</p>
        ) : (
          <ul className="flex flex-col gap-2">
            {cuentas.map((cuenta) => (
              <li
                key={cuenta.id}
                className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-borde bg-fondo px-3 py-2"
              >
                <div className="min-w-0">
                  <p className="font-medium">
                    {cuenta.nombre}
                    {cuenta.es_usted && <span className="text-texto-suave"> (tú)</span>}
                  </p>
                  <p className="truncate text-sm text-texto-suave">{cuenta.email}</p>
                  <p className="text-sm text-texto-suave">
                    {ETIQUETA_ROL[cuenta.rol] ?? 'Sin rol'}
                    {cuenta.sede && ` · ${cuenta.sede}`}
                  </p>
                </div>
                <div className="flex items-center gap-3">
                  <span
                    className={`rounded-full border px-2 py-0.5 text-xs font-medium ${
                      cuenta.activa ? 'border-exito text-exito' : 'border-aviso text-aviso'
                    }`}
                  >
                    {cuenta.activa ? 'Activa' : 'Desactivada'}
                  </span>
                  {cuenta.es_usted ? (
                    <span className="text-sm text-texto-suave">No puedes desactivar tu cuenta</span>
                  ) : (
                    <Boton
                      variante={cuenta.activa ? 'peligro' : 'secundario'}
                      onClick={() => cambiarEstado(cuenta)}
                      cargando={procesando === cuenta.id}
                      aria-label={`${cuenta.activa ? 'Desactivar' : 'Reactivar'} la cuenta de ${cuenta.nombre}`}
                    >
                      {cuenta.activa ? 'Desactivar' : 'Reactivar'}
                    </Boton>
                  )}
                </div>
              </li>
            ))}
          </ul>
        )}
      </Tarjeta>
    </div>
  )
}
