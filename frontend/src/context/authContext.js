import { createContext } from 'react'

/** Holds { user, status, login, logout, can, ... }. Provided by <AuthProvider>, read with useAuth(). */
export const AuthContext = createContext(null)
