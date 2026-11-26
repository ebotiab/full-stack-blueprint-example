import { expect, test } from '@playwright/test'

test.beforeEach(async ({ page }) => {
  await page.route('**/api/auth/me', (route) =>
    route.fulfill({ json: { id: 1, email: 'visitor@example.com', is_admin: false } }),
  )
  await page.route('**/api/messages', (route) => route.fulfill({ json: [] }))
})

const execution = {
  model: 'openai/gpt-oss-20b',
  duration_ms: 123,
  model_requests: 2,
  tool_used: true,
  rows_read: 4,
  input_tokens: 100,
  output_tokens: 25,
  cost_usd: '0.00001',
  trace_id: '12345678901234567890123456789012',
  commit: 'abc1234',
}

test('sends suggestions and a continuation, displays real response metadata', async ({ page }) => {
  const requests: unknown[] = []
  await page.route('**/api/demo-chat', async (route) => {
    if (route.request().method() === 'GET') {
      await route.fulfill({ json: { available: true, remaining: 5, detail: 'Ready.' } })
    } else {
      requests.push(route.request().postDataJSON())
      await route.fulfill({
        json: { answer: 'A summary from the model.', remaining: 5 - requests.length, execution },
      })
    }
  })
  await page.goto('/')
  await page.getByRole('button', { name: 'Read the stored messages and summarize them.' }).click()
  await page.getByRole('button', { name: 'Send', exact: true }).click()
  await expect(page.getByRole('list', { name: 'Conversation' })).toContainText(
    'A summary from the model.',
  )
  await page.getByRole('list', { name: 'Conversation' }).getByText('Inside this response').click()
  await expect(page.getByText('PostgreSQL tool', { exact: false })).toBeVisible()
  await expect(page.getByText('123 ms', { exact: false })).toBeVisible()
  await page.getByLabel('Your message').fill('Make that shorter.')
  await page.getByRole('button', { name: 'Send', exact: true }).click()
  await expect(page.getByRole('list', { name: 'Conversation' }).getByRole('listitem')).toHaveCount(
    2,
  )
  expect(requests).toEqual([
    { message: 'Read the stored messages and summarize them.' },
    { message: 'Make that shorter.' },
  ])
})

test('does not present an unconfigured chat as operational', async ({ page }) => {
  await page.route('**/api/demo-chat', (route) =>
    route.fulfill({ json: { available: false, remaining: 5, detail: 'Chat is not activated.' } }),
  )
  await page.goto('/')
  await expect(page.getByRole('status')).toContainText('not activated')
  await expect(page.getByRole('button', { name: 'Send', exact: true })).toBeDisabled()
})

for (const [code, text] of [
  [429, 'quota'],
  [502, 'Gateway'],
  [503, 'not been activated'],
  [504, 'too long'],
] as const) {
  test(`explains error ${code} without retries`, async ({ page }) => {
    let posts = 0
    await page.route('**/api/demo-chat', async (route) => {
      if (route.request().method() === 'GET')
        await route.fulfill({ json: { available: true, remaining: 5, detail: 'Ready.' } })
      else {
        posts++
        await route.fulfill({ status: code, json: { detail: 'not displayed raw' } })
      }
    })
    await page.goto('/')
    await page.getByLabel('Your message').fill('Hi')
    await page.getByRole('button', { name: 'Send', exact: true }).click()
    await expect(page.getByRole('alert')).toContainText(text)
    expect(posts).toBe(1)
  })
}

test('disables duplicate submissions while waiting, then enforces the session cap', async ({
  page,
}) => {
  let release: (() => void) | undefined
  const gate = new Promise<void>((resolve) => {
    release = resolve
  })
  await page.route('**/api/demo-chat', async (route) => {
    if (route.request().method() === 'GET')
      await route.fulfill({ json: { available: true, remaining: 1, detail: 'Ready.' } })
    else {
      await gate
      await route.fulfill({ json: { answer: 'Done', remaining: 0, execution } })
    }
  })
  await page.goto('/')
  await page.getByLabel('Your message').fill('Hi')
  await page.getByRole('button', { name: 'Send', exact: true }).click()
  await expect(page.getByRole('button', { name: 'Thinking…', exact: true })).toBeDisabled()
  release?.()
  await expect(page.getByRole('status')).toContainText('Session limit reached')
  await expect(page.getByRole('button', { name: 'Send', exact: true })).toBeDisabled()
})
