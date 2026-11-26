// A fresh browser against the real deployment. No mocked requests or Vercel bypass token.
// Run from the repository root after the providers report the intended deployments live:
//   node scripts/verify-live-demo.mjs
import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import { createRequire } from 'node:module'

const require = createRequire(new URL('../frontend/package.json', import.meta.url))
const { chromium } = require('@playwright/test')
const readme = await readFile(new URL('../README.md', import.meta.url), 'utf8')
const demoUrl = readme.match(/\[Open the live demo\]\((https:\/\/[^)]+)\)/)?.[1]
const docsUrl = readme.match(/\[Public API documentation\]\((https:\/\/[^)]+)\)/)?.[1]
assert.ok(demoUrl && docsUrl, 'README must provide the public demo and API documentation links')

const browser = await chromium.launch({
  proxy: process.env.HTTPS_PROXY ? { server: process.env.HTTPS_PROXY } : undefined,
})
const context = await browser.newContext()
const page = await context.newPage()
const pageErrors = []
const serverErrors = []
page.on('pageerror', (error) => pageErrors.push(error.message))
page.on('response', (response) => {
  if (response.status() >= 500) serverErrors.push(`${response.status()} ${response.url()}`)
})

try {
  // Follow the actual README link, starting without cookies for GitHub, Vercel or this app.
  await page.goto('https://github.com/ebotiab/full-stack-blueprint-example', { timeout: 120_000 })
  const link = page.getByRole('link', { name: 'Open the live demo', exact: true })
  assert.equal(await link.getAttribute('href'), demoUrl)
  await link.click()
  await page.waitForURL(`${demoUrl}/`, { timeout: 120_000 })
  const button = page.getByRole('button', { name: 'Try the demo', exact: true })
  await button.waitFor({ timeout: 120_000 })
  assert.equal((await context.cookies()).some((cookie) => cookie.name === '__Host-session'), false)

  const loginResult = page.waitForResponse((response) => response.url().endsWith('/api/auth/login'))
  await button.click()
  const login = await loginResult
  assert.equal(login.status(), 200)
  assert.equal((await login.json()).is_admin, false)
  const list = page.getByRole('list', { name: 'Messages' })
  await list.waitFor()
  const originalMessages = await list.innerText()
  assert.ok(originalMessages.includes('Hello from PostgreSQL'))
  const session = (await context.cookies()).find((cookie) => cookie.name === '__Host-session')
  assert.ok(session?.httpOnly && session.secure && session.sameSite === 'Lax')

  const health = await context.request.get(`${demoUrl}/api/healthz`)
  assert.equal(health.status(), 200)
  const serving = await health.json()
  assert.match(serving.commit, /^[a-f0-9]{40}$/)
  if (process.env.EXPECTED_API_COMMIT) assert.equal(serving.commit, process.env.EXPECTED_API_COMMIT)
  const messages = await context.request.get(`${demoUrl}/api/messages`)
  assert.equal(messages.status(), 200)
  assert.equal(messages.headers()['cache-control'], 'no-store')
  const data = await messages.json()
  assert.ok(data.length >= 4)
  await page.reload()
  await list.waitFor()
  assert.equal(await list.innerText(), originalMessages, 'Data and the session survive a reload')
  assert.deepEqual(await (await context.request.get(`${demoUrl}/api/messages`)).json(), data)

  const anonymous = await browser.newContext()
  assert.equal((await anonymous.request.get(`${demoUrl}/api/messages`)).status(), 401)
  await anonymous.close()
  // Refusing an invalid password change proves the read-only guard without risking a password change.
  assert.equal((await context.request.post(`${demoUrl}/api/auth/password`, {
    headers: { 'Sec-Fetch-Site': 'same-origin' },
    data: { current_password: 'deliberately-invalid', new_password: 'never-applied-password' },
  })).status(), 403)

  if (process.env.DEMO_SCREENSHOT) await page.screenshot({ path: process.env.DEMO_SCREENSHOT, fullPage: true })
  const logoutResult = page.waitForResponse((response) => response.url().endsWith('/api/auth/logout'))
  await page.getByRole('button', { name: 'Sign out', exact: true }).click()
  assert.equal((await logoutResult).status(), 204)
  await button.waitFor()
  assert.equal((await context.request.get(`${demoUrl}/api/auth/me`)).status(), 401)
  assert.equal((await context.cookies()).some((cookie) => cookie.name === '__Host-session'), false)

  await page.goto(docsUrl)
  await page.getByRole('heading', { name: /My Project API/ }).waitFor()
  const schema = await context.request.get(`${demoUrl}/openapi.json`)
  assert.equal(schema.status(), 200)
  assert.ok((await schema.json()).paths['/api/messages'])
  assert.deepEqual(pageErrors, [], 'No browser runtime errors')
  assert.deepEqual(serverErrors, [], 'No server errors during the visitor journey')
  console.log(JSON.stringify({ demoUrl, docsUrl, apiCommit: serving.commit, messages: data.length, result: 'passed' }))
} finally {
  await context.close()
  await browser.close()
}
