import { beforeEach, describe, expect, it, vi } from 'vitest'
import { googleLogin, login, register, registerAndLogin } from './auth-api'

const fetchMock = vi.fn<(req: Request) => Promise<Response>>()
const tokens = { access_token: 'a', refresh_token: 'r', token_type: 'bearer' }

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status })
}

async function sent(n: number) {
  const r = fetchMock.mock.calls[n][0]
  return { method: r.method, path: new URL(r.url).pathname, body: await r.json() }
}

beforeEach(() => {
  localStorage.clear()
  fetchMock.mockReset()
  vi.stubGlobal('fetch', fetchMock)
})

describe('auth api', () => {
  it('login posts credentials to /auth/login', async () => {
    fetchMock.mockResolvedValue(json(tokens))
    await expect(login('a@b.co', 'pw')).resolves.toEqual(tokens)
    expect(await sent(0)).toEqual({
      method: 'POST',
      path: '/auth/login',
      body: { email: 'a@b.co', password: 'pw' },
    })
  })

  it('register posts to /auth/register', async () => {
    fetchMock.mockResolvedValue(json({ id: '1', email: 'a@b.co' }, 201))
    await register('a@b.co', 'pw')
    expect((await sent(0)).path).toBe('/auth/register')
  })

  it('registerAndLogin registers then logs in', async () => {
    fetchMock.mockResolvedValueOnce(json({ id: '1' }, 201)).mockResolvedValueOnce(json(tokens))
    await expect(registerAndLogin('a@b.co', 'pw')).resolves.toEqual(tokens)
    expect((await sent(0)).path).toBe('/auth/register')
    expect((await sent(1)).path).toBe('/auth/login')
  })

  it('registerAndLogin skips login if registration fails', async () => {
    fetchMock.mockResolvedValue(json({ detail: 'email taken' }, 409))
    await expect(registerAndLogin('a@b.co', 'pw')).rejects.toMatchObject({
      status: 409,
      message: 'email taken',
    })
    expect(fetchMock).toHaveBeenCalledTimes(1)
  })

  it('googleLogin posts the id token', async () => {
    fetchMock.mockResolvedValue(json(tokens))
    await googleLogin('idtok')
    expect(await sent(0)).toMatchObject({ path: '/auth/google', body: { id_token: 'idtok' } })
  })
})
