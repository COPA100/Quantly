import { createContext, useContext } from 'react'
import type { TokenPair } from './types'

export interface AuthState {
  isAuthenticated: boolean
  login: (tokens: TokenPair) => void
  logout: () => void
}

export const AuthContext = createContext<AuthState | null>(null)

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext)
  if (!ctx) {
    throw new Error('useAuth must be used within AuthProvider')
  }
  return ctx
}
