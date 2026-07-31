import { apiFetch } from './api'
import type { TokenPair, User } from './types'

export function login(email: string, password: string): Promise<TokenPair> {
  return apiFetch<TokenPair>('/auth/login', {
    method: 'POST',
    body: JSON.stringify({ email, password }),
  })
}

export function register(email: string, password: string): Promise<User> {
  return apiFetch<User>('/auth/register', {
    method: 'POST',
    body: JSON.stringify({ email, password }),
  })
}

export async function registerAndLogin(email: string, password: string): Promise<TokenPair> {
  await register(email, password)
  return login(email, password)
}
