import axios from 'axios'
import { leerSesion } from '../auth/sesionGuardada.js'

// Cliente HTTP único para hablar con el backend de Django.
// La URL base se configura en frontend/.env con VITE_API_URL.
const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL ?? 'http://127.0.0.1:8000/api',
  timeout: 10000,
})

// Agrega el token JWT a cada petición cuando hay sesión iniciada.
api.interceptors.request.use((config) => {
  const token = leerSesion()?.token
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

export default api
