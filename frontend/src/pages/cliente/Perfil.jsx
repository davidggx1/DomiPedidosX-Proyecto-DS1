import { useEffect, useState } from 'react'
import { interpretarError } from '../../api/errores.js'
import { actualizarPerfil, obtenerPerfil } from '../../api/usuarios.js'
import { useAuth } from '../../auth/useAuth.js'
import Alerta from '../../components/ui/Alerta.jsx'
import Boton from '../../components/ui/Boton.jsx'
import CampoTexto from '../../components/ui/CampoTexto.jsx'
import Tarjeta from '../../components/ui/Tarjeta.jsx'
import { validarPerfil } from '../../utils/perfil.js'

const VACIO = { nombres: '', apellidos: '', celular: '' }

// HU-07 · The customer updates his name and phone. A new phone is checked
// again with the same rules as the registration (10 digits, not used by another account)
export default function Perfil() {
  const { actualizarUsuario } = useAuth()
  const [perfil, setPerfil] = useState(null)
  const [datos, setDatos] = useState(VACIO)
  const [errores, setErrores] = useState({})
  const [errorGeneral, setErrorGeneral] = useState(null)
  const [guardando, setGuardando] = useState(false)
  const [guardado, setGuardado] = useState(false)

  useEffect(() => {
    let vigente = true
    obtenerPerfil()
      .then((leido) => {
        if (!vigente) return
        setPerfil(leido)
        setDatos({ nombres: leido.nombres, apellidos: leido.apellidos, celular: leido.celular })
      })
      .catch((fallo) => {
        if (vigente) setErrorGeneral(interpretarError(fallo).general)
      })
    return () => {
      vigente = false
    }
  }, [])

  function cambiar(evento) {
    const { name, value } = evento.target
    setDatos((actuales) => ({ ...actuales, [name]: value }))
    setErrores((actuales) => ({ ...actuales, [name]: undefined }))
    setGuardado(false)
  }

  async function guardar(evento) {
    evento.preventDefault()
    setErrorGeneral(null)
    setGuardado(false)
    const encontrados = validarPerfil(datos)
    setErrores(encontrados)
    if (Object.keys(encontrados).length > 0) return

    setGuardando(true)
    try {
      const actualizado = await actualizarPerfil({
        nombres: datos.nombres.trim(),
        apellidos: datos.apellidos.trim(),
        celular: datos.celular.trim(),
      })
      setPerfil(actualizado)
      setDatos({ nombres: actualizado.nombres, apellidos: actualizado.apellidos, celular: actualizado.celular })
      // the header shows the new name without logging in again
      actualizarUsuario({ nombre: `${actualizado.nombres} ${actualizado.apellidos}` })
      setGuardado(true)
    } catch (fallo) {
      const { general, campos } = interpretarError(fallo)
      setErrores(campos)
      if (Object.keys(campos).length === 0) setErrorGeneral(general)
    } finally {
      setGuardando(false)
    }
  }

  const sinCambios =
    perfil &&
    datos.nombres.trim() === perfil.nombres &&
    datos.apellidos.trim() === perfil.apellidos &&
    datos.celular.trim() === perfil.celular

  return (
    <div className="flex max-w-xl flex-col gap-4">
      <header>
        <h1 className="text-2xl font-bold">Mi perfil</h1>
        <p className="text-texto-suave">Actualiza tu nombre y tu número de contacto.</p>
      </header>

      {errorGeneral && <Alerta tipo="error" titulo={errorGeneral} />}
      {!perfil && !errorGeneral && <p className="text-texto-suave">Cargando…</p>}

      {perfil && (
        <>
          <Tarjeta titulo="Datos de la cuenta">
            <dl className="flex flex-col gap-1 text-sm">
              <div className="flex flex-wrap justify-between gap-2">
                <dt className="text-texto-suave">Correo</dt>
                <dd>{perfil.email}</dd>
              </div>
              <div className="flex flex-wrap justify-between gap-2">
                <dt className="text-texto-suave">Documento</dt>
                <dd>
                  {perfil.tipo_documento} {perfil.num_documento}
                </dd>
              </div>
            </dl>
          </Tarjeta>

          <Tarjeta titulo="Datos de contacto">
            <form onSubmit={guardar} noValidate className="flex flex-col gap-4">
              <CampoTexto
                etiqueta="Nombres"
                name="nombres"
                autoComplete="given-name"
                requerido
                value={datos.nombres}
                onChange={cambiar}
                error={errores.nombres}
              />
              <CampoTexto
                etiqueta="Apellidos"
                name="apellidos"
                autoComplete="family-name"
                requerido
                value={datos.apellidos}
                onChange={cambiar}
                error={errores.apellidos}
              />
              <CampoTexto
                etiqueta="Celular"
                name="celular"
                type="tel"
                inputMode="numeric"
                autoComplete="tel-national"
                maxLength={10}
                requerido
                value={datos.celular}
                onChange={cambiar}
                error={errores.celular}
                ayuda="10 dígitos, sin espacios. Debe ser un número que no use otra cuenta."
              />

              {guardado && <Alerta tipo="exito" titulo="Tus datos se guardaron." />}

              <Boton tipo="submit" cargando={guardando} disabled={sinCambios} className="self-start">
                Guardar cambios
              </Boton>
            </form>
          </Tarjeta>
        </>
      )}
    </div>
  )
}
