import { http, HttpResponse } from 'msw'
import { afterEach, beforeEach, describe, expect, it } from 'vitest'
import { API } from '../test/handlers'
import { server } from '../test/server'
import { client } from './client'

beforeEach(() => {
  localStorage.clear()
})

describe('client request interceptor', () => {
  it('attaches the bearer token from localStorage when present', async () => {
    localStorage.setItem('access_token', 'tok-abc')
    let auth: string | null = null
    server.use(
      http.get(`${API}/auth/me`, ({ request }) => {
        auth = request.headers.get('authorization')
        return HttpResponse.json({ ok: true })
      }),
    )
    await client.get('/auth/me')
    expect(auth).toBe('Bearer tok-abc')
  })

  it('omits the Authorization header when no token is stored', async () => {
    let auth: string | null = 'sentinel'
    server.use(
      http.get(`${API}/auth/me`, ({ request }) => {
        auth = request.headers.get('authorization')
        return HttpResponse.json({ ok: true })
      }),
    )
    await client.get('/auth/me')
    expect(auth).toBeNull()
  })
})

describe('client 401 → refresh flow', () => {
  it('refreshes on 401, stores new tokens, and retries with the new bearer', async () => {
    localStorage.setItem('access_token', 'stale')
    localStorage.setItem('refresh_token', 'rt-1')

    let refreshBody: { refresh_token?: string } | null = null
    const seenAuth: string[] = []
    server.use(
      http.post(`${API}/auth/refresh`, async ({ request }) => {
        refreshBody = (await request.json()) as { refresh_token?: string }
        return HttpResponse.json({ access_token: 'fresh', refresh_token: 'rt-2', token_type: 'bearer' })
      }),
      http.get(`${API}/auth/me`, ({ request }) => {
        const auth = request.headers.get('authorization') ?? ''
        seenAuth.push(auth)
        if (auth === 'Bearer fresh') return HttpResponse.json({ id: 'u1' })
        return new HttpResponse(null, { status: 401 })
      }),
    )

    const res = await client.get('/auth/me')
    expect(res.data).toEqual({ id: 'u1' })
    expect(refreshBody).toEqual({ refresh_token: 'rt-1' })
    expect(localStorage.getItem('access_token')).toBe('fresh')
    expect(localStorage.getItem('refresh_token')).toBe('rt-2')
    // first call carried the stale token, retry carried the fresh one
    expect(seenAuth).toEqual(['Bearer stale', 'Bearer fresh'])
  })

  it('coalesces concurrent 401s into a single refresh; all retries succeed', async () => {
    localStorage.setItem('access_token', 'stale')
    localStorage.setItem('refresh_token', 'rt-1')

    let refreshCount = 0
    server.use(
      http.post(`${API}/auth/refresh`, async () => {
        refreshCount += 1
        // Small delay so both requests observe `refreshing === true`.
        await new Promise((r) => setTimeout(r, 20))
        return HttpResponse.json({ access_token: 'fresh', refresh_token: 'rt-2', token_type: 'bearer' })
      }),
      http.get(`${API}/auth/me`, ({ request }) => {
        const auth = request.headers.get('authorization') ?? ''
        if (auth === 'Bearer fresh') return HttpResponse.json({ ok: 'me' })
        return new HttpResponse(null, { status: 401 })
      }),
      http.get(`${API}/projects/`, ({ request }) => {
        const auth = request.headers.get('authorization') ?? ''
        if (auth === 'Bearer fresh') return HttpResponse.json({ ok: 'projects' })
        return new HttpResponse(null, { status: 401 })
      }),
    )

    const [a, b] = await Promise.all([client.get('/auth/me'), client.get('/projects/')])
    expect(a.data).toEqual({ ok: 'me' })
    expect(b.data).toEqual({ ok: 'projects' })
    expect(refreshCount).toBe(1)
  })

  it('clears tokens and rejects when the refresh endpoint returns 401', async () => {
    // NB: don't replace window.location — axios reads it to resolve request
    // URLs, so a stub without an origin breaks every request. client.ts only
    // *sets* location.href on failure, which jsdom logs (doesn't throw), and
    // it runs after the token-clearing lines anyway.
    localStorage.setItem('access_token', 'stale')
    localStorage.setItem('refresh_token', 'rt-bad')

    server.use(
      http.get(`${API}/auth/me`, () => HttpResponse.json({ detail: 'unauthorized' }, { status: 401 })),
      http.post(`${API}/auth/refresh`, () =>
        HttpResponse.json({ detail: 'expired' }, { status: 401 }),
      ),
    )

    await expect(client.get('/auth/me')).rejects.toBeDefined()
    expect(localStorage.getItem('access_token')).toBeNull()
    expect(localStorage.getItem('refresh_token')).toBeNull()
  })

  it('rejects and clears tokens when there is no refresh token on 401', async () => {
    localStorage.setItem('access_token', 'stale')
    // no refresh_token set

    server.use(
      http.get(`${API}/auth/me`, () => HttpResponse.json({ detail: 'unauthorized' }, { status: 401 })),
    )

    await expect(client.get('/auth/me')).rejects.toBeDefined()
    expect(localStorage.getItem('access_token')).toBeNull()
    expect(localStorage.getItem('refresh_token')).toBeNull()
  })
})

afterEach(() => {
  localStorage.clear()
})
