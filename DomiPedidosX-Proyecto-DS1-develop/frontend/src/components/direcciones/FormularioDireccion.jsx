import { useEffect, useRef, useState } from 'react'
import { actualizarDireccion, crearDireccion } from '../../api/direcciones.js'
import { interpretarError } from '../../api/errores.js'
import { buscarDireccion, direccionDesdeCoordenadas } from '../../api/geocodificacion.js'
import Alerta from '../ui/Alerta.jsx'
import Boton from '../ui/Boton.jsx'
import CampoTexto from '../ui/CampoTexto.jsx'
import Casilla from '../ui/Casilla.jsx'
import MapaUbicacion from './MapaUbicacion.jsx'

const VACIO = { alias: '', direccion: '', barrio: '', indicaciones: '', es_principal: false }

function valoresIniciales(direccion) {
  if (!direccion) return VACIO
  return {
    alias: direccion.alias,
    direccion: direccion.direccion,
    barrio: direccion.barrio ?? '',
    indicaciones: direccion.indicaciones ?? '',
    es_principal: direccion.es_principal,
  }
}

// Quién llenó por última vez cada campo que el mapa puede deducir:
// 'usuario' (lo escribió), 'mapa' (vino del pin) o null (vacío).
// El mapa solo reemplaza lo que no escribió el usuario.
const CAMPOS_DEL_MAPA = ['direccion', 'barrio']
const ETIQUETA_CAMPO = { direccion: 'la dirección', barrio: 'el barrio' }

function origenInicial(direccion) {
  return {
    direccion: direccion?.direccion ? 'usuario' : null,
    barrio: direccion?.barrio ? 'usuario' : null,
  }
}

// Nomenclatura colombiana: "Carrera 17D" sin "# 20-15" no dice a qué casa ir.
const EMPIEZA_CON_VIA = /^(avenida\s+)?(calle|carrera|diagonal|transversal|avenida|circular|autopista|cl|cll|cra|kr|cr|dg|tv|av)\.?\s*\d/i
const TIENE_NUMERO_DE_CASA = /#|\bn(o|º|°)\.?\s*\d/i

function faltaNumeroDeCasa(texto) {
  const limpio = texto.trim()
  return EMPIEZA_CON_VIA.test(limpio) && !TIENE_NUMERO_DE_CASA.test(limpio)
}

// Espera tras el último clic o arrastre antes de consultar: Nominatim pide máximo 1 consulta por segundo.
const ESPERA_CONSULTA_MS = 600

function posicionInicial(direccion) {
  return direccion ? { latitud: direccion.latitud, longitud: direccion.longitud } : null
}

// Seis decimales ≈ 10 cm: más precisión no aporta nada.
const redondear = (valor) => Math.round(valor * 1e6) / 1e6

// Con GPS (celular) suele quedar por debajo; con Wi-Fi o IP (computador), muy por encima.
const PRECISION_BUENA_METROS = 100

const formatearDistancia = (metros) =>
  metros < 1000 ? `±${Math.round(metros)} m` : `±${(metros / 1000).toFixed(1).replace('.', ',')} km`

// Entre menos precisa la ubicación, más alejada la vista, para que se vea el círculo completo.
const zoomSegunPrecision = (metros) => (metros <= PRECISION_BUENA_METROS ? 18 : metros <= 1000 ? 15 : 13)

const ERRORES_UBICACION = {
  1: 'No diste permiso para usar tu ubicación. Puedes activarlo en el candado de la barra de direcciones, o buscar tu dirección.',
  2: 'No pudimos obtener tu ubicación en este dispositivo. Busca tu dirección o haz clic en el mapa.',
  3: 'Obtener tu ubicación tardó demasiado. Inténtalo de nuevo o busca tu dirección.',
}

// Mismas reglas que el backend, para avisar antes de enviar.
function validar(valores, posicion, confirmada) {
  const errores = {}
  if (!valores.alias.trim()) errores.alias = 'Ponle un nombre, por ejemplo "Casa".'
  if (!valores.direccion.trim()) errores.direccion = 'Escribe la dirección.'
  if (!posicion) {
    errores.ubicacion = 'Ubica la dirección en el mapa: usa tu ubicación, búscala o haz clic en el punto exacto.'
  } else if (!confirmada) {
    errores.ubicacion = 'Confirma que el pin está en el lugar de entrega.'
  }
  return errores
}

// Formulario para crear o editar una dirección de entrega (HU-06).
// El pin se ubica con la ubicación actual del dispositivo, buscando la dirección
// o haciendo clic en el mapa. Si lo ubicó el sistema, el cliente confirma que es
// el lugar correcto (o lo mueve). Se guardan el texto y las coordenadas.
// El padre debe darle una `key` distinta al cambiar de dirección para reiniciarlo.
export default function FormularioDireccion({ direccion, alGuardar, alCancelar }) {
  const esEdicion = Boolean(direccion)
  const [valores, setValores] = useState(() => valoresIniciales(direccion))
  const [origen, setOrigen] = useState(() => origenInicial(direccion))
  const [posicion, setPosicion] = useState(() => posicionInicial(direccion))
  const [enfoque, setEnfoque] = useState(() => posicionInicial(direccion))
  // Una dirección ya guardada se considera confirmada.
  const [confirmada, setConfirmada] = useState(esEdicion)
  const [precision, setPrecision] = useState(null)
  const [avisoUbicacion, setAvisoUbicacion] = useState(null)
  const [localizando, setLocalizando] = useState(false)
  const [resultados, setResultados] = useState(null)
  const [sugerencia, setSugerencia] = useState(null)
  // Último cambio que hizo el mapa en los campos, para poder deshacerlo.
  const [actualizacion, setActualizacion] = useState(null)
  const [consultandoPunto, setConsultandoPunto] = useState(false)
  const [buscando, setBuscando] = useState(false)
  const [errorMapa, setErrorMapa] = useState(null)
  const [errores, setErrores] = useState({})
  const [errorGeneral, setErrorGeneral] = useState(null)
  const [guardando, setGuardando] = useState(false)
  // Solo cuenta la respuesta de la última vez que se movió el pin.
  const ultimaConsulta = useRef(0)
  const temporizador = useRef(null)
  // Cómo estaba el pin antes de moverlo, para que "Deshacer" lo devuelva junto con los textos.
  // Si el cliente hace varios clics antes de que responda el mapa, se guarda el estado previo al primero.
  const pinAnterior = useRef(null)
  // Valores vigentes para la respuesta del mapa, que llega después del render.
  const estadoActual = useRef({ valores, origen })

  useEffect(() => {
    estadoActual.current = { valores, origen }
  })

  useEffect(() => () => clearTimeout(temporizador.current), [])

  function cambiar(evento) {
    const { name, value, type, checked } = evento.target
    setValores((actuales) => ({ ...actuales, [name]: type === 'checkbox' ? checked : value }))
    if (CAMPOS_DEL_MAPA.includes(name)) {
      // Si lo borra, el mapa puede volver a llenarlo.
      setOrigen((actual) => ({ ...actual, [name]: value.trim() ? 'usuario' : null }))
      setActualizacion(null)
    }
  }

  // Descarta una consulta al mapa que siga pendiente, para que no llene campos de un punto viejo.
  function cancelarConsulta() {
    ultimaConsulta.current += 1
    clearTimeout(temporizador.current)
    setConsultandoPunto(false)
    pinAnterior.current = null
  }

  function guardarPinAnterior() {
    pinAnterior.current ??= { posicion, confirmada, precision }
  }

  // Pone en los campos lo que dedujo el mapa, sin tocar lo que escribió el usuario.
  // Devuelve los campos que no se pudieron actualizar por haberlos escrito el usuario.
  function aplicarDelMapa(deducidos) {
    const pin = pinAnterior.current
    pinAnterior.current = null
    const { valores: actuales, origen: origenActual } = estadoActual.current
    const cambios = {}
    const protegidos = {}
    for (const campo of CAMPOS_DEL_MAPA) {
      if (!(campo in deducidos)) continue
      const nuevo = deducidos[campo] ?? ''
      if (nuevo === actuales[campo]) continue
      if (!nuevo) {
        // El nuevo punto no tiene ese dato: lo que puso el mapa para el punto anterior ya no aplica.
        if (origenActual[campo] === 'mapa') cambios[campo] = ''
      } else if (origenActual[campo] === 'usuario') {
        protegidos[campo] = nuevo
      } else {
        cambios[campo] = nuevo
      }
    }
    const campos = Object.keys(cambios)
    if (campos.length > 0) {
      setActualizacion({
        texto: `Actualizamos ${campos.map((campo) => ETIQUETA_CAMPO[campo]).join(' y ')} según el pin.`,
        anteriores: Object.fromEntries(campos.map((campo) => [campo, actuales[campo]])),
        origenAnterior: Object.fromEntries(campos.map((campo) => [campo, origenActual[campo]])),
        pin,
        // Sin texto ni pin previos no hay nada que deshacer.
        sePuedeDeshacer: Boolean(pin?.posicion) || campos.some((campo) => actuales[campo]),
      })
      setValores((v) => ({ ...v, ...cambios }))
      setOrigen((o) => ({
        ...o,
        ...Object.fromEntries(campos.map((campo) => [campo, cambios[campo] ? 'mapa' : null])),
      }))
    } else {
      setActualizacion(null)
    }
    return protegidos
  }

  // Deshace el último movimiento completo: textos, pin y su confirmación vuelven a como estaban.
  function deshacerActualizacion() {
    const { anteriores, origenAnterior, pin } = actualizacion
    cancelarConsulta()
    setValores((v) => ({ ...v, ...anteriores }))
    setOrigen((o) => ({ ...o, ...origenAnterior }))
    if (pin) {
      setPosicion(pin.posicion)
      setConfirmada(pin.confirmada)
      setPrecision(pin.precision)
      if (pin.posicion) setEnfoque({ ...pin.posicion, zoom: 17 })
    }
    setAvisoUbicacion(null)
    setSugerencia(null)
    setActualizacion(null)
  }

  async function buscar() {
    const texto = valores.direccion.trim()
    if (!texto) {
      setErrores((actuales) => ({ ...actuales, direccion: 'Escribe la dirección que quieres buscar.' }))
      return
    }
    setBuscando(true)
    setErrorMapa(null)
    try {
      setResultados(await buscarDireccion(`${texto}, Cali`))
    } catch (error) {
      setErrorMapa(error.message)
    } finally {
      setBuscando(false)
    }
  }

  // Pone el pin en un punto. `confirmado` es true cuando lo ubicó el propio cliente.
  function ubicarPin(punto, { confirmado, enfocarConZoom = null, radio = null }) {
    setPosicion({ latitud: punto.latitud, longitud: punto.longitud })
    if (enfocarConZoom) setEnfoque({ ...punto, zoom: enfocarConZoom })
    setConfirmada(confirmado)
    setPrecision(radio)
    setResultados(null)
    setErrores((actuales) => ({ ...actuales, ubicacion: undefined }))
  }

  // El texto que escribió el cliente para buscar no se reemplaza; el barrio sigue la regla general.
  function elegirResultado(resultado) {
    cancelarConsulta()
    guardarPinAnterior()
    ubicarPin(resultado, { confirmado: false, enfocarConZoom: 17 })
    setAvisoUbicacion(null)
    setSugerencia(null)
    aplicarDelMapa({ barrio: resultado.barrio })
  }

  function usarMiUbicacion() {
    // Fuera de HTTPS (o localhost) el navegador no entrega la ubicación.
    if (!navigator.geolocation || !window.isSecureContext) {
      setAvisoUbicacion({
        tipo: 'aviso',
        texto: 'Este navegador no permite obtener tu ubicación aquí. Busca tu dirección o haz clic en el mapa.',
      })
      return
    }
    setLocalizando(true)
    setAvisoUbicacion(null)
    navigator.geolocation.getCurrentPosition(
      ({ coords }) => {
        setLocalizando(false)
        const punto = { latitud: coords.latitude, longitud: coords.longitude }
        const precisa = coords.accuracy <= PRECISION_BUENA_METROS
        // Solo la ubicación precisa consulta el mapa; la imprecisa no actualiza textos que deshacer.
        cancelarConsulta()
        if (precisa) guardarPinAnterior()
        ubicarPin(punto, {
          confirmado: false,
          enfocarConZoom: zoomSegunPrecision(coords.accuracy),
          radio: coords.accuracy,
        })
        // La precisión la reporta el navegador y no siempre es cierta (algunos de
        // computador dicen "±1 m" en un punto equivocado): no se muestra como garantía.
        setAvisoUbicacion(
          precisa
            ? {
                tipo: 'info',
                texto: 'Te ubicamos. Revisa en el mapa que el pin esté en tu puerta; si no, muévelo.',
              }
            : {
                tipo: 'aviso',
                texto: `Tu ubicación es aproximada (${formatearDistancia(coords.accuracy)}), algo común en computadores. Busca tu dirección o mueve el pin al lugar exacto.`,
              },
        )
        // Con una ubicación imprecisa, el texto sugerido sería de otra calle.
        if (precisa) sugerirTexto(punto.latitud, punto.longitud)
      },
      (error) => {
        setLocalizando(false)
        setAvisoUbicacion({ tipo: 'aviso', texto: ERRORES_UBICACION[error.code] ?? ERRORES_UBICACION[2] })
      },
      { enableHighAccuracy: true, timeout: 15000, maximumAge: 60000 },
    )
  }

  // Clic o arrastre: el cliente eligió el punto, así que queda confirmado.
  function moverPin(latitud, longitud) {
    guardarPinAnterior()
    ubicarPin({ latitud, longitud }, { confirmado: true })
    setAvisoUbicacion(null)
    sugerirTexto(latitud, longitud)
  }

  // Deduce dirección y barrio del punto. Espera a que el pin se quede quieto.
  function sugerirTexto(latitud, longitud) {
    const consulta = ++ultimaConsulta.current
    clearTimeout(temporizador.current)
    setSugerencia(null)
    setConsultandoPunto(true)
    temporizador.current = setTimeout(async () => {
      try {
        const encontrada = await direccionDesdeCoordenadas(latitud, longitud)
        if (consulta !== ultimaConsulta.current || !encontrada) return
        const protegidos = aplicarDelMapa({ direccion: encontrada.texto, barrio: encontrada.barrio })
        if (Object.keys(protegidos).length > 0) setSugerencia(protegidos)
      } catch {
        // La sugerencia es opcional: si falla, el pin igual queda ubicado.
      } finally {
        if (consulta === ultimaConsulta.current) setConsultandoPunto(false)
      }
    }, ESPERA_CONSULTA_MS)
  }

  // El usuario acepta reemplazar su texto por lo que dedujo el mapa.
  function usarSugerencia() {
    setValores((v) => ({ ...v, ...sugerencia }))
    setOrigen((o) => ({ ...o, ...Object.fromEntries(Object.keys(sugerencia).map((campo) => [campo, 'mapa'])) }))
    setSugerencia(null)
  }

  async function enviar(evento) {
    evento.preventDefault()
    const nuevosErrores = validar(valores, posicion, confirmada)
    setErrores(nuevosErrores)
    setErrorGeneral(null)
    if (Object.keys(nuevosErrores).length > 0) return

    const datos = {
      alias: valores.alias.trim(),
      direccion: valores.direccion.trim(),
      barrio: valores.barrio.trim(),
      indicaciones: valores.indicaciones.trim(),
      latitud: redondear(posicion.latitud),
      longitud: redondear(posicion.longitud),
      es_principal: valores.es_principal,
    }

    setGuardando(true)
    try {
      const guardada = esEdicion
        ? await actualizarDireccion(direccion.id, datos)
        : await crearDireccion(datos)
      alGuardar(guardada, esEdicion)
    } catch (error) {
      const { general, campos } = interpretarError(error)
      setErrorGeneral(general)
      setErrores({ ...campos, ubicacion: campos.latitud ?? campos.longitud })
    } finally {
      setGuardando(false)
    }
  }

  const textoSugerido = sugerencia && [sugerencia.direccion, sugerencia.barrio].filter(Boolean).join(' · ')

  return (
    <form noValidate onSubmit={enviar} className="flex flex-col gap-4">
      <h2 className="text-lg font-bold">
        {esEdicion ? `Editar "${direccion.alias}"` : 'Nueva dirección'}
      </h2>

      {errorGeneral && <Alerta tipo="error" titulo={errorGeneral} />}

      <CampoTexto
        etiqueta="Nombre"
        name="alias"
        value={valores.alias}
        onChange={cambiar}
        error={errores.alias}
        placeholder="Ej.: Casa, Oficina"
        maxLength={50}
        requerido
      />

      <div className="flex flex-col gap-2 sm:flex-row sm:items-start">
        <CampoTexto
          etiqueta="Dirección"
          name="direccion"
          value={valores.direccion}
          onChange={cambiar}
          onKeyDown={(evento) => {
            if (evento.key === 'Enter') {
              evento.preventDefault()
              buscar()
            }
          }}
          error={errores.direccion}
          ayuda="Vía y número de la casa. El apartamento y las referencias van en Indicaciones."
          placeholder="Ej.: Calle 5 # 38-20"
          maxLength={255}
          requerido
          className="flex-1"
        />
        <Boton variante="secundario" onClick={buscar} cargando={buscando} className="sm:mt-6">
          Buscar en el mapa
        </Boton>
      </div>
      {faltaNumeroDeCasa(valores.direccion) && (
        <p className="-mt-2 text-sm text-aviso">
          Completa el número de la casa, por ejemplo {valores.direccion.trim()} # 20-15. Así el repartidor sabe a
          qué puerta ir.
        </p>
      )}

      {resultados && (
        <div className="flex flex-col gap-2" aria-live="polite">
          {resultados.length === 0 ? (
            <p className="text-sm text-texto-suave">
              No encontramos esa dirección. Prueba solo con la calle y el barrio, o ubica el pin a mano.
            </p>
          ) : (
            <>
              <p className="text-sm font-medium">Elige la coincidencia más cercana:</p>
              <ul className="flex flex-col gap-1">
                {resultados.map((resultado) => (
                  <li key={resultado.id}>
                    <button
                      type="button"
                      onClick={() => elegirResultado(resultado)}
                      className="w-full rounded-lg border border-borde bg-fondo px-3 py-2 text-left text-sm hover:bg-superficie-alta"
                    >
                      {resultado.nombre}
                    </button>
                  </li>
                ))}
              </ul>
            </>
          )}
        </div>
      )}

      {errorMapa && <Alerta tipo="aviso" titulo={errorMapa} />}

      <div className="flex flex-col gap-2">
        <p className="text-sm font-medium">
          Ubicación en el mapa
          <span className="text-marca-clara" aria-hidden="true"> *</span>
        </p>
        <p className="text-sm text-texto-suave">
          Usa tu ubicación actual, busca la dirección o haz clic en el punto exacto. El repartidor llegará a
          este punto.
        </p>
        <Boton
          variante="secundario"
          onClick={usarMiUbicacion}
          cargando={localizando}
          className="self-start"
        >
          Usar mi ubicación actual
        </Boton>
        {avisoUbicacion && <Alerta tipo={avisoUbicacion.tipo} titulo={avisoUbicacion.texto} />}
        <MapaUbicacion
          posicion={posicion}
          enfoque={enfoque}
          precision={precision}
          alCambiar={moverPin}
        />
        {posicion && !confirmada && (
          <div className="flex flex-wrap items-center gap-3 rounded-lg border border-aviso bg-fondo px-3 py-2">
            <p className="flex-1 text-sm">
              <span className="font-semibold">¿El pin está en el lugar de entrega?</span> Si no, arrástralo o
              haz clic en el punto correcto.
            </p>
            <Boton onClick={() => {
              setConfirmada(true)
              setErrores((actuales) => ({ ...actuales, ubicacion: undefined }))
            }}>
              Sí, es aquí
            </Boton>
          </div>
        )}
        {posicion && confirmada && (
          <p className="text-sm text-exito">✓ Ubicación confirmada. Puedes mover el pin si necesitas corregirla.</p>
        )}
        {errores.ubicacion && (
          <p role="alert" className="text-sm text-error">
            {errores.ubicacion}
          </p>
        )}
        <div aria-live="polite" className="flex flex-col gap-1">
          {consultandoPunto && (
            <p className="text-sm text-texto-suave">Buscando la dirección de este punto…</p>
          )}
          {!consultandoPunto && actualizacion && (
            <p className="text-sm text-texto-suave">
              {actualizacion.texto}{' '}
              {actualizacion.sePuedeDeshacer && (
                <button
                  type="button"
                  onClick={deshacerActualizacion}
                  className="font-medium text-marca-clara underline"
                >
                  Deshacer
                </button>
              )}
            </p>
          )}
          {!consultandoPunto && textoSugerido && (
            <p className="text-sm text-texto-suave">
              El mapa ubica este punto en <span className="text-texto">{textoSugerido}</span>.{' '}
              <button type="button" onClick={usarSugerencia} className="font-medium text-marca-clara underline">
                Usar esta dirección
              </button>
            </p>
          )}
        </div>
      </div>

      <CampoTexto
        etiqueta="Barrio"
        name="barrio"
        value={valores.barrio}
        onChange={cambiar}
        error={errores.barrio}
        placeholder="Opcional"
        maxLength={50}
      />

      {/* El mapa nunca toca este campo: solo el cliente sabe cuál es su puerta. */}
      <CampoTexto
        etiqueta="Indicaciones para el repartidor"
        name="indicaciones"
        value={valores.indicaciones}
        onChange={cambiar}
        error={errores.indicaciones}
        ayuda="Apartamento, torre, portería o cómo reconocer el lugar. Opcional."
        placeholder="Ej.: Apto 301, torre B, portería norte"
        maxLength={200}
      />

      <Casilla
        etiqueta="Usar como dirección principal"
        name="es_principal"
        checked={valores.es_principal}
        onChange={cambiar}
      />

      <div className="flex flex-wrap gap-3">
        <Boton tipo="submit" cargando={guardando}>
          {esEdicion ? 'Guardar cambios' : 'Guardar dirección'}
        </Boton>
        {esEdicion && (
          <Boton variante="fantasma" onClick={alCancelar}>
            Cancelar
          </Boton>
        )}
      </div>
    </form>
  )
}
