import { createContext } from 'react'

// Contexto con el usuario actual y las acciones de sesión.
// Se consume con el hook useAuth().
export const AuthContext = createContext(null)
