import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

// Mock the axios instance so no network is hit and we can assert request shaping.
const post = vi.fn()
const get = vi.fn()
vi.mock('../lib/client', () => ({ client: { post: (...a: unknown[]) => post(...a), get: (...a: unknown[]) => get(...a) } }))

import {
  clearTokens,
  isAuthenticated,
  login,
  logout,
  register,
  saveTokens,
  type TokenResponse,
} from './auth'

const tokens: TokenResponse = {
  access_token: 'acc',
  refresh_token: 'ref',
  token_type: 'bearer',
}

beforeEach(() => {
  localStorage.clear()
  post.mockReset()
  get.mockReset()
})

afterEach(() => {
  localStorage.clear()
})

describe('token storage helpers', () => {
  it('saveTokens persists both tokens and isAuthenticated reflects it', () => {
    expect(isAuthenticated()).toBe(false)
    saveTokens(tokens)
    expect(localStorage.getItem('access_token')).toBe('acc')
    expect(localStorage.getItem('refresh_token')).toBe('ref')
    expect(isAuthenticated()).toBe(true)
  })

  it('clearTokens removes them', () => {
    saveTokens(tokens)
    clearTokens()
    expect(localStorage.getItem('access_token')).toBeNull()
    expect(isAuthenticated()).toBe(false)
  })
})

describe('login', () => {
  it('posts form-urlencoded username/password and returns the token body', async () => {
    post.mockResolvedValue({ data: tokens })
    const result = await login('a@b.com', 'pw')

    expect(result).toEqual(tokens)
    expect(post).toHaveBeenCalledTimes(1)
    const [url, body, config] = post.mock.calls[0]
    expect(url).toBe('/auth/token')
    expect(body).toBeInstanceOf(URLSearchParams)
    expect((body as URLSearchParams).get('username')).toBe('a@b.com')
    expect((body as URLSearchParams).get('password')).toBe('pw')
    expect(config.headers['Content-Type']).toBe('application/x-www-form-urlencoded')
  })
})

describe('register', () => {
  it('posts a JSON body including the optional org name', async () => {
    post.mockResolvedValue({ data: tokens })
    await register('a@b.com', 'pw', 'Acme')
    expect(post).toHaveBeenCalledWith('/auth/register', {
      email: 'a@b.com',
      password: 'pw',
      org_name: 'Acme',
    })
  })
})

describe('logout', () => {
  it('revokes the stored refresh token and clears storage even on success', async () => {
    saveTokens(tokens)
    post.mockResolvedValue({ data: {} })
    await logout()
    expect(post).toHaveBeenCalledWith('/auth/revoke', { refresh_token: 'ref' })
    expect(localStorage.getItem('access_token')).toBeNull()
  })

  it('clears tokens even when revoke fails', async () => {
    saveTokens(tokens)
    post.mockRejectedValue(new Error('network'))
    await expect(logout()).rejects.toThrow('network')
    expect(localStorage.getItem('access_token')).toBeNull()
    expect(localStorage.getItem('refresh_token')).toBeNull()
  })
})
