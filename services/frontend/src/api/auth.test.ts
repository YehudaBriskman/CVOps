import { renderHook, waitFor } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { describe, expect, it } from 'vitest'
import { API } from '../test/handlers'
import { server } from '../test/server'
import { withQueryClient } from '../test/utils'
import { login, logout, register, saveTokens, useMe } from './auth'

describe('auth api', () => {
  it('login posts form-encoded credentials and returns tokens', async () => {
    let contentType: string | null = null
    server.use(
      http.post(`${API}/auth/token`, ({ request }) => {
        contentType = request.headers.get('content-type')
        return HttpResponse.json({
          access_token: 'a', refresh_token: 'r', token_type: 'bearer',
        })
      }),
    )
    const tokens = await login('u@test.com', 'pw')
    expect(tokens.access_token).toBe('a')
    expect(contentType).toContain('application/x-www-form-urlencoded')
  })

  it('register posts JSON body and returns tokens', async () => {
    const tokens = await register('u@test.com', 'pw', 'Org')
    expect(tokens.refresh_token).toBe('refresh-1')
  })

  it('logout clears tokens even after revoke', async () => {
    saveTokens({ access_token: 'a', refresh_token: 'r', token_type: 'bearer' })
    await logout()
    expect(localStorage.getItem('access_token')).toBeNull()
    expect(localStorage.getItem('refresh_token')).toBeNull()
  })

  it('useMe fetches the current user when authenticated', async () => {
    localStorage.setItem('access_token', 'a')
    const { result } = renderHook(() => useMe(), { wrapper: withQueryClient() })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(result.current.data?.email).toBe('u@test.com')
  })
})
