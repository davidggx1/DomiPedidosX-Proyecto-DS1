import { formatearPrecio } from '../../utils/formato.js'

// Colores del destello detrás de la foto (hex + alfa para el degradado).
const PALETAS = {
  rojo: { base: '#e11d2e', suave: '#e11d2e80', tenue: '#e11d2e33' },
  lima: { base: '#d4e600', suave: '#d4e60066', tenue: '#d4e60030' },
  ambar: { base: '#f59e0b', suave: '#f59e0b73', tenue: '#f59e0b33' },
}
const ORDEN = ['rojo', 'lima', 'ambar']

const SIN_ACENTOS = (texto) =>
  texto.toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, '')

// Palabras del producto que fijan el color; si no hay, se rota por id.
function paletaDe(producto) {
  const texto = SIN_ACENTOS(producto.nombre ?? '')
  if (/limon|lima|maracuya|pina|mango/.test(texto)) return PALETAS.lima
  if (/gaseosa|cola|fresa|tomate|doble|bbq|picante/.test(texto)) return PALETAS.rojo
  if (/clasica|queso|papa|pollo|naranja/.test(texto)) return PALETAS.ambar
  return PALETAS[ORDEN[Number(producto.id) % ORDEN.length] ?? 'rojo']
}

// Tarjeta de producto del menú del cliente: texto a la izquierda, foto a la derecha
// sobre un destello de color. Si no está disponible, bloquea el botón.
export default function TarjetaProducto({ producto, alAgregar }) {
  const { nombre, precio, imagen, disponible } = producto
  const paleta = paletaDe(producto)

  return (
    <article className="relative isolate min-h-60 rounded-2xl border border-white/10 bg-[#17151a] text-white shadow-lg">
      {/* Destello: fondo con degradado y franja diagonal, recortado a la tarjeta. */}
      <div aria-hidden="true" className="absolute inset-0 -z-10 overflow-hidden rounded-2xl">
        <div
          className="absolute inset-0"
          style={{
            background: `radial-gradient(circle at 78% 55%, ${paleta.suave}, transparent 60%)`,
          }}
        />
        <div
          className="absolute -right-6 -top-10 h-[150%] w-28 rotate-[28deg]"
          style={{
            background: `linear-gradient(180deg, ${paleta.tenue}, transparent 85%)`,
          }}
        />
      </div>

      {/* Foto: sobresale un poco por arriba de la tarjeta. */}
      {imagen ? (
        <img
          src={imagen}
          alt={`Foto de ${nombre}`}
          loading="lazy"
          className={`pointer-events-none absolute -top-8 -bottom-6 right-0 h-[calc(100%+3.5rem)] w-[60%] object-contain object-center drop-shadow-[0_12px_20px_rgba(0,0,0,0.6)] ${
            disponible ? '' : 'opacity-50 grayscale'
          }`} 
        />
      ) : (
        <div
          aria-hidden="true"
          className="absolute right-4 top-1/2 size-24 -translate-y-1/2 rounded-full bg-white/5"
        />
      )}

      <div className="relative flex h-full min-h-60 w-[48%] flex-col justify-center gap-2 p-5">
        <h3 className="font-titulo text-xl font-bold leading-tight sm:text-2xl">{nombre}</h3>

        {!disponible && (
          <span className="w-fit rounded-full border border-aviso px-2 py-0.5 text-xs font-medium text-aviso">
            No disponible
          </span>
        )}

        <p className="font-titulo text-xl font-semibold sm:text-2xl">{formatearPrecio(precio)}</p>

        <button
          type="button"
          onClick={() => alAgregar?.(producto)}
          disabled={!disponible}
          aria-label={disponible ? `Agregar ${nombre} al carrito` : `${nombre} no está disponible`}
          className="mt-1 inline-flex min-h-11 w-fit items-center gap-2 rounded-full bg-gradient-to-b from-[#f03a3a] to-[#c9170f] py-2 pl-5 pr-3 font-titulo font-semibold text-white shadow-[0_6px_16px_rgba(225,29,46,0.4)] transition hover:brightness-110 disabled:cursor-not-allowed disabled:opacity-50 disabled:shadow-none"
        >
          Agregar
          <span
            aria-hidden="true"
            className="flex size-6 items-center justify-center rounded-full bg-white text-lg font-bold leading-none text-[#c9170f]"
          >
            +
          </span>
        </button>
      </div>
    </article>
  )
}