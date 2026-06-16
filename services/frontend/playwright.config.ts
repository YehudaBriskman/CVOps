import { defineConfig, devices } from '@playwright/test'

/**
 * E2E against the LIVE dev stack (tilt up): nginx edge at http://localhost
 * proxying the host API + Vite. Tests do NOT spin the stack up — start it with
 * `tilt up` first, then `npm run e2e`. global-setup registers a throwaway org +
 * user via the API and writes its tokens into a storageState so authed specs
 * start logged in (the app keeps JWTs in localStorage, not cookies).
 */
export default defineConfig({
  testDir: './e2e',
  fullyParallel: false,
  workers: 1,
  retries: process.env.CI ? 1 : 0,
  reporter: [['list']],
  globalSetup: './e2e/global-setup.ts',
  use: {
    baseURL: 'http://localhost',
    storageState: './e2e/.auth/state.json',
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
})
