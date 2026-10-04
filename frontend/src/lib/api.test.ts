import { beforeEach, describe, expect, it, vi } from 'vitest'
import { ApiError, AUTH_EXPIRED_EVENT, apiFetch, errorMessage } from './api'
import { getAccessToken, getRefreshToken, setTokens } from './auth'

const fetchMock = vi.fn<(req: Request | string, init?: RequestInit) => Promise<Response>>()

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

// the request passed to the nth fetch call
function req(n: number): Request {
  return fetchMock.mock.calls[n][0] as Request
}

const newTokens = { access_token: 'new', refresh_token: 'ref2', token_type: 'bearer' }

beforeEach(() => {
  localStorage.clear()
  fetchMock.mockReset()
  vi.stubGlobal('fetch', fetchMock)
})

describe('apiFetch requests', () => {
  it('sends no auth header when logged out', async () => {
    fetchMock.mockResolvedValue(json({ ok: true }))
    await apiFetch('/ping')
    expect(req(0).headers.get('Authorization')).toBeNull()
    expect(req(0).url).toMatch(/\/ping$/)
  })

  it('attaches the bearer token when logged in', async () => {
    setTokens({ access_token: 'tok', refresh_token: 'ref', token_type: 'bearer' })
    fetchMock.mockResolvedValue(json({}))
    await apiFetch('/me')
    expect(req(0).headers.get('Authorization')).toBe('Bearer tok')
  })

  it('sets json content type only when there is a non-form body', async () => {
    fetchMock.mockImplementation(async () => json({}))
    await apiFetch('/a', { method: 'POST', body: JSON.stringify({ x: 1 }) })
    await apiFetch('/b')
    expect(req(0).headers.get('Content-Type')).toBe('application/json')
    expect(req(1).headers.get('Content-Type')).toBeNull()
  })

  it('leaves content type to the browser for form data', async () => {
    fetchMock.mockResolvedValue(json({}))
    const form = new FormData()
    form.append('file', new Blob(['x']), 'x.csv')
    await apiFetch('/upload', { method: 'POST', body: form })
    expect(req(0).headers.get('Content-Type')).toMatch(/^multipart\/form-data/)
  })
})

describe('apiFetch responses', () => {
  it('parses a json body', async () => {
    fetchMock.mockResolvedValue(json({ id: 7 }))
    await expect(apiFetch<{ id: number }>('/x')).resolves.toEqual({ id: 7 })
  })

  it('returns undefined on 204', async () => {
    fetchMock.mockResolvedValue(new Response(null, { status: 204 }))
    await expect(apiFetch('/x', { method: 'DELETE' })).resolves.toBeUndefined()
  })

  it('throws ApiError with the backend detail', async () => {
    fetchMock.mockResolvedValue(json({ detail: 'nope' }, 422))
    const err = (await apiFetch('/x').catch((e: unknown) => e)) as ApiError
    expect(err).toBeInstanceOf(ApiError)
    expect(err.status).toBe(422)
    expect(err.message).toBe('nope')
  })

  it('falls back to status text when the error body is not json', async () => {
    fetchMock.mockResolvedValue(new Response('boom', { status: 500, statusText: 'Server Error' }))
    const err = (await apiFetch('/x').catch((e: unknown) => e)) as ApiError
    expect(err).toBeInstanceOf(ApiError)
    expect(err.message).toBe('Server Error')
  })

  it('does not try to refresh on 401 without a refresh token', async () => {
    fetchMock.mockResolvedValue(json({ detail: 'bad creds' }, 401))
    await expect(apiFetch('/auth/login')).rejects.toMatchObject({
      status: 401,
      message: 'bad creds',
    })
    expect(fetchMock).toHaveBeenCalledTimes(1)
  })
})

describe('apiFetch refresh on 401', () => {
  beforeEach(() => {
    setTokens({ access_token: 'old', refresh_token: 'ref', token_type: 'bearer' })
  })

  it('refreshes once and replays the request with the new token', async () => {
    fetchMock
      .mockResolvedValueOnce(json({ detail: 'expired' }, 401))
      .mockResolvedValueOnce(json(newTokens))
      .mockResolvedValueOnce(json({ ok: 1 }))

    await expect(apiFetch('/me')).resolves.toEqual({ ok: 1 })

    expect(fetchMock).toHaveBeenCalledTimes(3)
    expect(String(fetchMock.mock.calls[1][0])).toMatch(/\/auth\/refresh$/)
    expect(JSON.parse(fetchMock.mock.calls[1][1]?.body as string)).toEqual({ refresh_token: 'ref' })
    expect(req(2).headers.get('Authorization')).toBe('Bearer new')
    expect(getAccessToken()).toBe('new')
    expect(getRefreshToken()).toBe('ref2')
  })

  it('replays a request body after refresh', async () => {
    fetchMock
      .mockResolvedValueOnce(json({}, 401))
      .mockResolvedValueOnce(json(newTokens))
      .mockResolvedValueOnce(json({}))
    await apiFetch('/p', { method: 'POST', body: JSON.stringify({ a: 1 }) })
    expect(await req(2).text()).toBe('{"a":1}')
  })

  it('shares one refresh across concurrent 401s', async () => {
    fetchMock.mockImplementation(async (r) => {
      if (String(typeof r === 'string' ? r : r.url).endsWith('/auth/refresh')) {
        return json(newTokens)
      }
      const auth = (r as Request).headers.get('Authorization')
      return auth === 'Bearer new' ? json({ ok: true }) : json({}, 401)
    })

    await Promise.all([apiFetch('/a'), apiFetch('/b'), apiFetch('/c')])

    const refreshCalls = fetchMock.mock.calls.filter(([r]) => String(r).endsWith('/auth/refresh'))
    expect(refreshCalls).toHaveLength(1)
  })

  it('clears tokens and fires the expired event when refresh fails', async () => {
    const onExpired = vi.fn()
    window.addEventListener(AUTH_EXPIRED_EVENT, onExpired)
    fetchMock
      .mockResolvedValueOnce(json({ detail: 'expired' }, 401))
      .mockResolvedValueOnce(json({ detail: 'bad refresh' }, 401))

    await expect(apiFetch('/me')).rejects.toMatchObject({ status: 401 })

    expect(onExpired).toHaveBeenCalledTimes(1)
    expect(getAccessToken()).toBeNull()
    expect(getRefreshToken()).toBeNull()
    window.removeEventListener(AUTH_EXPIRED_EVENT, onExpired)
  })

  it('does not loop when the replay is also a 401', async () => {
    fetchMock
      .mockResolvedValueOnce(json({}, 401))
      .mockResolvedValueOnce(json(newTokens))
      .mockResolvedValueOnce(json({ detail: 'still no' }, 401))
    await expect(apiFetch('/me')).rejects.toMatchObject({ status: 401, message: 'still no' })
    expect(fetchMock).toHaveBeenCalledTimes(3)
  })
})

describe('errorMessage', () => {
  it('uses the message of an ApiError', () => {
    expect(errorMessage(new ApiError(400, 'bad email'))).toBe('bad email')
  })

  it('hides unknown errors behind a generic message', () => {
    const generic = 'Something went wrong. Please try again.'
    expect(errorMessage(new Error('secret internals'))).toBe(generic)
    expect(errorMessage('str')).toBe(generic)
  })
})
