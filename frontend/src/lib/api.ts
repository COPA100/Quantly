import { clearTokens, getAccessToken, getRefreshToken, setTokens } from './auth'
import { API_URL } from './config'
import type { TokenPair } from './types'

// fired when a refresh attempt fails; AuthProvider listens and drops the session
export const AUTH_EXPIRED_EVENT = 'quantly:auth-expired'

export class ApiError extends Error {
  status: number

  constructor(status: number, message: string) {
    super(message)
    this.status = status
    this.name = 'ApiError'
  }
}

function buildRequest(path: string, options: RequestInit): Request {
  const headers = new Headers(options.headers)
  const isFormData = options.body instanceof FormData
  if (options.body != null && !isFormData) {
    headers.set('Content-Type', 'application/json')
  }
  const token = getAccessToken()
  if (token) {
    headers.set('Authorization', `Bearer ${token}`)
  }
  return new Request(`${API_URL}${path}`, { ...options, headers })
}

// a single in-flight refresh shared by every 401'd request, so a burst of
// concurrent calls rotates the refresh token exactly once
let refreshInFlight: Promise<boolean> | null = null

async function performRefresh(): Promise<boolean> {
  const refresh = getRefreshToken()
  if (!refresh) return false
  const res = await fetch(`${API_URL}/auth/refresh`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ refresh_token: refresh }),
  })
  if (!res.ok) return false
  setTokens((await res.json()) as TokenPair)
  return true
}

function refreshOnce(): Promise<boolean> {
  refreshInFlight ??= performRefresh().finally(() => {
    refreshInFlight = null
  })
  return refreshInFlight
}

export async function apiFetch<T>(path: string, options: RequestInit = {}): Promise<T> {
  let res = await fetch(buildRequest(path, options))

  // access token likely expired: rotate once and replay the request
  if (res.status === 401 && getRefreshToken()) {
    if (await refreshOnce()) {
      res = await fetch(buildRequest(path, options))
    } else {
      clearTokens()
      window.dispatchEvent(new Event(AUTH_EXPIRED_EVENT))
    }
  }

  if (!res.ok) {
    const body = (await res.json().catch(() => null)) as { detail?: string } | null
    throw new ApiError(res.status, body?.detail ?? res.statusText)
  }
  if (res.status === 204) {
    return undefined as T
  }
  return res.json() as Promise<T>
}

export function errorMessage(err: unknown): string {
  if (err instanceof ApiError) {
    return err.message
  }
  return 'Something went wrong. Please try again.'
}
