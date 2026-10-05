import { fileURLToPath } from 'node:url'
import { expect, test } from '@playwright/test'

const SAMPLE = fileURLToPath(new URL('../../example_csv/ex1.csv', import.meta.url))

test('register, upload a portfolio, and see it analyzed', async ({ page }) => {
  const email = `e2e-${Date.now()}@example.com`

  await page.goto('/register')
  await page.getByLabel('Email').fill(email)
  await page.getByLabel('Password').fill('correct-horse-battery')
  await page.getByRole('button', { name: 'Create account' }).click()
  await expect(page.getByRole('heading', { name: 'Portfolios' })).toBeVisible()

  await page.getByRole('link', { name: 'Upload' }).first().click()
  await page.locator('input[type="file"]').setInputFiles(SAMPLE)
  await page.getByRole('button', { name: 'Analyze' }).click()

  // the detail page streams status over sse (or polls) until the worker finishes
  await expect(page).toHaveURL(/\/portfolios\/\d+$/)
  await expect(page.getByText('complete', { exact: true })).toBeVisible({ timeout: 120_000 })

  await expect(page.getByRole('heading', { name: 'Overview' })).toBeVisible()
  await expect(page.getByText('Total value', { exact: true })).toBeVisible()

  await expect(page.getByRole('heading', { name: 'Risk & performance' })).toBeVisible()
  await expect(page.getByText('Sharpe ratio', { exact: true })).toBeVisible()
  await expect(page.getByText('Max drawdown', { exact: true })).toBeVisible()
  // the risk card, not the var methods section further down
  await expect(page.getByText(/Value at risk/).first()).toBeVisible()

  await expect(page.getByRole('heading', { name: 'Correlation' })).toBeVisible()
  // newer analyzers. seeded history is ~400 days, too short for the stress
  // scenarios, and factor data needs the network, so neither is asserted here.
  await expect(page.getByRole('heading', { name: 'Value at risk methods' })).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Efficient frontier' })).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Risk contribution' })).toBeVisible()
  // eight holdings in the sample book, each a row and column label in the heatmap
  await expect(page.getByText('AAPL').first()).toBeVisible()
})

test('an invalid file is rejected with a message, not a crash', async ({ page }) => {
  await page.goto('/register')
  await page.getByLabel('Email').fill(`e2e-bad-${Date.now()}@example.com`)
  await page.getByLabel('Password').fill('correct-horse-battery')
  await page.getByRole('button', { name: 'Create account' }).click()
  await page.getByRole('link', { name: 'Upload' }).first().click()

  await page.locator('input[type="file"]').setInputFiles({
    name: 'bad.csv',
    mimeType: 'text/csv',
    buffer: Buffer.from('not,a,portfolio\n1,2,3\n'),
  })
  await page.getByRole('button', { name: 'Analyze' }).click()
  await expect(page.locator('p.text-red-600')).toBeVisible()
})
