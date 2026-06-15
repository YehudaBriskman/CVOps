import { expect, test } from '@playwright/test'

// Uses the authed storageState from global-setup (default in playwright.config).

test.describe('projects', () => {
  test('create a project and open it', async ({ page }) => {
    const name = `E2E Project ${Date.now()}`

    await page.goto('/projects')
    await expect(page.getByRole('heading', { name: 'Projects', level: 2 })).toBeVisible()

    await page.getByRole('button', { name: '+ New Project' }).first().click()
    await page.getByPlaceholder('My project').fill(name)
    await page.getByRole('button', { name: 'Create' }).click()

    // the new project card shows up in the list
    const card = page.getByText(name, { exact: true })
    await expect(card).toBeVisible()

    // opening it navigates into the project workspace
    await card.click()
    await expect(page).toHaveURL(/\/projects\/[0-9a-f-]+$/)
  })

  test('the project shows its lifecycle sub-pages', async ({ page }) => {
    const name = `E2E Nav ${Date.now()}`
    await page.goto('/projects')
    await page.getByRole('button', { name: '+ New Project' }).first().click()
    await page.getByPlaceholder('My project').fill(name)
    await page.getByRole('button', { name: 'Create' }).click()
    await page.getByText(name, { exact: true }).click()

    const projectUrl = page.url()
    const id = projectUrl.split('/projects/')[1]

    // data-sources and samples pages render without error for the new project
    await page.goto(`/projects/${id}/data-sources`)
    await expect(page.locator('body')).not.toContainText('Application error')
    await page.goto(`/projects/${id}/samples`)
    await expect(page.locator('body')).not.toContainText('Application error')
  })
})
