import { expect, test } from '@playwright/test'

// Fresh, unauthenticated context — exercise the real register/login flow
// rather than the pre-seeded storageState.
test.use({ storageState: { cookies: [], origins: [] } })

test.describe('authentication', () => {
  test('register a new workspace lands on an empty projects page', async ({ page }) => {
    const email = `e2e-ui+${Date.now()}@cvopsqa.com`

    await page.goto('/register')
    await page.getByPlaceholder('you@example.com').fill(email)
    await page.getByPlaceholder('••••••••').fill('e2e-password-123')
    // unique org name — org names are unique per registration
    await page.getByPlaceholder('My Team').fill(`UI Test Org ${Date.now()}`)
    await page.getByRole('button', { name: 'Create account' }).click()

    await expect(page).toHaveURL(/\/projects$/)
    // the page's own H2 (the Layout header also renders an H1 "Projects")
    await expect(page.getByRole('heading', { name: 'Projects', level: 2 })).toBeVisible()
    // brand-new org → no projects yet
    await expect(page.getByText('No projects yet')).toBeVisible()
  })

  test('an unauthenticated visit to a protected route redirects to login', async ({ page }) => {
    await page.goto('/projects')
    await expect(page).toHaveURL(/\/login$/)
    await expect(page.getByRole('button', { name: 'Sign in' })).toBeVisible()
  })

  test('login with bad credentials does not authenticate and stays on login', async ({ page }) => {
    await page.goto('/login')
    await page.getByPlaceholder('you@example.com').fill('nobody@cvopsqa.com')
    await page.getByPlaceholder('••••••••').fill('wrong-password')
    await page.getByRole('button', { name: 'Sign in' }).click()

    // The 401 from /auth/token is caught by the axios client's refresh
    // interceptor, which (finding no refresh token) redirects to /login — so
    // rather than the inline error persisting, the user ends up back on the
    // login screen, unauthenticated and with no tokens stored.
    await expect(page).toHaveURL(/\/login$/)
    await expect(page.getByRole('button', { name: 'Sign in' })).toBeVisible()
    const token = await page.evaluate(() => localStorage.getItem('access_token'))
    expect(token).toBeNull()
  })
})
