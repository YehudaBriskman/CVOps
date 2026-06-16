import { mkdirSync, writeFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import { request, type FullConfig } from '@playwright/test'

const HERE = dirname(fileURLToPath(import.meta.url))
const STATE_PATH = resolve(HERE, '.auth/state.json')
const CREDS_PATH = resolve(HERE, '.auth/creds.json')

/**
 * Register a throwaway org + user against the live API and persist:
 *  - a Playwright storageState seeding localStorage with the JWTs (authed specs)
 *  - the raw credentials (so specs can re-login or seed data via the API)
 *
 * Uses Playwright's APIRequestContext rather than node's fetch: the dev edge
 * binds `localhost` in a way node/undici resolves inconsistently (IPv6 ::1),
 * whereas Playwright's networking matches what the browser uses.
 */
async function globalSetup(config: FullConfig) {
  const baseURL = config.projects[0]?.use?.baseURL ?? 'http://localhost'
  const stamp = Date.now()
  const email = `e2e+${stamp}@cvopsqa.com`
  const password = 'e2e-password-123'
  const orgName = `E2E Org ${stamp}`

  const ctx = await request.newContext({ baseURL })
  const res = await ctx.post('/api/v1/auth/register', {
    data: { email, password, org_name: orgName },
  })
  if (!res.ok()) {
    throw new Error(`global-setup: register failed (${res.status()}): ${await res.text()}`)
  }
  const tokens = (await res.json()) as { access_token: string; refresh_token: string }
  await ctx.dispose()

  const storageState = {
    cookies: [],
    origins: [
      {
        origin: 'http://localhost',
        localStorage: [
          { name: 'access_token', value: tokens.access_token },
          { name: 'refresh_token', value: tokens.refresh_token },
        ],
      },
    ],
  }

  mkdirSync(dirname(STATE_PATH), { recursive: true })
  writeFileSync(STATE_PATH, JSON.stringify(storageState, null, 2))
  writeFileSync(CREDS_PATH, JSON.stringify({ email, password, ...tokens }, null, 2))
}

export default globalSetup
