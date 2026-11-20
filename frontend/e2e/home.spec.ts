import { expect, test } from '@playwright/test'

// The test answers /api itself: it checks the visor, not the API (that is pytest's job).
test('lists the messages from the API', async ({ page }) => {
  await page.route('**/api/messages', (route) =>
    route.fulfill({
      json: [{ id: 1, text: 'Hello from the test', created_at: '2026-11-18T10:05:00Z' }],
    }),
  )
  await page.goto('/')
  const messages = page.getByRole('list', { name: 'Messages' })
  await expect(messages.getByRole('listitem')).toHaveText([
    'Hello from the test 18 Nov 2026, 10:05',
  ])
})

test('says so when the API does not answer', async ({ page }) => {
  await page.route('**/api/messages', (route) =>
    route.fulfill({ status: 503, json: { detail: 'down' } }),
  )
  await page.goto('/')
  await expect(page.getByRole('alert')).toContainText('The API is not responding')
})
