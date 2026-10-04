import { beforeEach, describe, expect, it } from 'vitest'
import {
  clearTokens,
  getAccessToken,
  getRefreshToken,
  isAuthenticated,
  setTokens,
} from './auth'

const pair = { access_token: 'a1', refresh_token: 'r1', token_type: 'bearer' }

beforeEach(() => localStorage.clear())

describe('token storage', () => {
  it('returns null when nothing is stored', () => {
    expect(getAccessToken()).toBeNull()
    expect(getRefreshToken()).toBeNull()
    expect(isAuthenticated()).toBe(false)
  })

  it('stores and reads both tokens', () => {
    setTokens(pair)
    expect(getAccessToken()).toBe('a1')
    expect(getRefreshToken()).toBe('r1')
    expect(isAuthenticated()).toBe(true)
  })

  it('overwrites on rotation', () => {
    setTokens(pair)
    setTokens({ ...pair, access_token: 'a2', refresh_token: 'r2' })
    expect(getAccessToken()).toBe('a2')
    expect(getRefreshToken()).toBe('r2')
  })

  it('clears both tokens', () => {
    setTokens(pair)
    clearTokens()
    expect(getAccessToken()).toBeNull()
    expect(getRefreshToken()).toBeNull()
    expect(isAuthenticated()).toBe(false)
  })
})
