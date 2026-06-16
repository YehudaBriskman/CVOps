import { http, HttpResponse } from 'msw'

// Base URL the test env pins client.ts to (see vitest.config.ts → test.env).
export const API = 'http://localhost/api/v1'

/**
 * Default happy-path handlers shared across tests. Individual tests override
 * any of these per-case with `server.use(...)` (see src/test/server.ts), which
 * takes precedence for the duration of that test.
 */
export const handlers = [
  // ── auth ───────────────────────────────────────────────────────────────
  http.post(`${API}/auth/token`, () =>
    HttpResponse.json({
      access_token: 'access-1',
      refresh_token: 'refresh-1',
      token_type: 'bearer',
    }),
  ),
  http.post(`${API}/auth/register`, () =>
    HttpResponse.json({
      access_token: 'access-1',
      refresh_token: 'refresh-1',
      token_type: 'bearer',
    }),
  ),
  http.post(`${API}/auth/revoke`, () => new HttpResponse(null, { status: 204 })),
  http.post(`${API}/auth/refresh`, () =>
    HttpResponse.json({ access_token: 'access-2', refresh_token: 'refresh-2', token_type: 'bearer' }),
  ),
  http.get(`${API}/auth/me`, () =>
    HttpResponse.json({ id: 'u1', email: 'u@test.com', org_id: 'o1' }),
  ),

  // ── projects ─────────────────────────────────────────────────────────────
  http.get(`${API}/projects/`, () => HttpResponse.json([])),
]
