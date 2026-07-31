import { type ReactNode, useCallback, useEffect, useMemo, useState } from 'react'
import { AUTH_EXPIRED_EVENT } from '../lib/api'
import { clearTokens, isAuthenticated as hasToken, setTokens } from '../lib/auth'
import { AuthContext } from '../lib/auth-context'
import type { TokenPair } from '../lib/types'

export default function AuthProvider({ children }: { children: ReactNode }) {
  const [authed, setAuthed] = useState(hasToken)

  const login = useCallback((tokens: TokenPair) => {
    setTokens(tokens)
    setAuthed(true)
  }, [])

  const logout = useCallback(() => {
    clearTokens()
    setAuthed(false)
  }, [])

  useEffect(() => {
    // a failed refresh (from the api interceptor) ends the session
    function onExpired() {
      setAuthed(false)
    }
    window.addEventListener(AUTH_EXPIRED_EVENT, onExpired)
    return () => window.removeEventListener(AUTH_EXPIRED_EVENT, onExpired)
  }, [])

  const value = useMemo(
    () => ({ isAuthenticated: authed, login, logout }),
    [authed, login, logout],
  )

  return <AuthContext value={value}>{children}</AuthContext>
}
