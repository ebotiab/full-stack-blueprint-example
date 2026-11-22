import { expect, test, type Page } from '@playwright/test'

// The test answers /api itself: it checks the form and what it shows. The sign-in rules
// (passwords, cookies, attempts) are pytest's job, in backend/tests/test_auth.py.
const user = { id: 1, email: 'ada@example.com', is_admin: false }

async function answerApi(page: Page, me: { status: number; json: object }) {
  await page.route('**/api/auth/me', (route) => route.fulfill(me))
  await page.route('**/api/messages', (route) =>
    route.fulfill({ json: [{ id: 1, text: 'Hello', created_at: '2026-11-18T10:05:00Z' }] }),
  )
}

async function fillAndSubmit(page: Page) {
  await page.getByLabel('Email').fill(user.email)
  await page.getByLabel('Password').fill('correct horse battery staple')
  await page.getByRole('button', { name: 'Sign in' }).click()
}

test('signs in and shows the messages', async ({ page }) => {
  await answerApi(page, { status: 401, json: { detail: 'Not signed in.' } })
  let sent: unknown
  await page.route('**/api/auth/login', (route) => {
    sent = route.request().postDataJSON()
    return route.fulfill({ json: user })
  })
  await page.goto('/')
  await fillAndSubmit(page)
  await expect(page.getByText(`Signed in as ${user.email}`)).toBeVisible()
  await expect(page.getByRole('list', { name: 'Messages' })).toBeVisible()
  expect(sent).toEqual({ email: user.email, password: 'correct horse battery staple' })
})

test('says so when the password is wrong', async ({ page }) => {
  await answerApi(page, { status: 401, json: { detail: 'Not signed in.' } })
  await page.route('**/api/auth/login', (route) =>
    route.fulfill({ status: 401, json: { detail: 'Wrong email or password.' } }),
  )
  await page.goto('/')
  await fillAndSubmit(page)
  await expect(page.getByRole('alert')).toHaveText('Wrong email or password.')
})

test('signs out', async ({ page }) => {
  await answerApi(page, { status: 200, json: user })
  await page.route('**/api/auth/logout', (route) => route.fulfill({ status: 204 }))
  await page.goto('/')
  await page.getByRole('button', { name: 'Sign out' }).click()
  await expect(page.getByRole('form', { name: 'Sign in' })).toBeVisible()
})
