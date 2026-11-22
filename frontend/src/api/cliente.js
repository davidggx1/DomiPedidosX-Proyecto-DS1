import axios from 'axios'
import { guardarSesionYAvisar, leerSesion } from '../auth/sesionGuardada.js'

// Cliente HTTP único para hablar con el backend de Django.
// La URL base se configura en frontend/.env con VITE_API_URL.
const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL ?? 'http://127.0.0.1:8000/api',
  // El backend gratis de Render se duerme y tarda cerca de 1 minuto en despertar (SCRUM-143)
  timeout: 70000,
})

// Agrega el token JWT a cada petición cuando hay sesión iniciada.
api.interceptors.request.use((config) => {
  const token = leerSesion()?.token
  if (token && !config.headers.Authorization) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// El token de acceso dura 30 minutos. Si una petición responde 401, se pide uno nuevo
// con el refresh token y se repite la petición una vez. Si tampoco se puede, la sesión
// expiró: se cierra y la app vuelve al login.
// Las peticiones con `sinRenovar: true` (login, renovación) no pasan por aquí.
let renovacionEnCurso = null

function renovarToken(refresh) {
  renovacionEnCurso ??= api
    .post('/auth/token/refresh/', { refresh }, { sinRenovar: true })
    .then(({ data }) => data.access)
    .finally(() => {
      renovacionEnCurso = null
    })
  return renovacionEnCurso
}

api.interceptors.response.use(
  (respuesta) => respuesta,
  async (error) => {
    const { config, response } = error
    const sesion = leerSesion()
    if (response?.status !== 401 || !config || config.sinRenovar || config._renovada || !sesion?.refresh) {
      throw error
    }

    let token
    try {
      token = await renovarToken(sesion.refresh)
    } catch {
      guardarSesionYAvisar(null, { expirada: true })
      throw error
    }

    const actual = leerSesion()
    if (!actual) throw error // se cerró la sesión mientras tanto
    guardarSesionYAvisar({ ...actual, token })
    config._renovada = true
    config.headers.Authorization = `Bearer ${token}`
    return api(config)
  },
)

export default api
