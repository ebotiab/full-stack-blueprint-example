// A fresh browser against the real deployment. No mocked requests or Vercel bypass token.
// Run from the repository root after the providers report the intended deployments live:
//   node scripts/verify-live-demo.mjs
import assert from 'node:assert/strict'
import { randomBytes } from 'node:crypto'
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

async function sendChat(chatPage, message) {
  await chatPage.getByLabel('Your message').fill(message)
  const reply = chatPage.waitForResponse(
    (response) => response.url().endsWith('/api/demo-chat') && response.request().method() === 'POST',
    { timeout: 60_000 },
  )
  await chatPage.getByRole('button', { name: 'Send', exact: true }).click()
  const response = await reply
  assert.equal(response.status(), 200)
  const turn = await response.json()
  assert.ok(turn.answer.length > 0)
  assert.match(turn.execution.trace_id, /^[a-f0-9]{32}$/)
  assert.ok(turn.execution.input_tokens > 0 && turn.execution.output_tokens > 0)
  return turn
}

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

  await page.getByRole('heading', { name: 'How the chat works' }).waitFor()

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

  let chatExecution = null
  if (process.env.VERIFY_CHAT === '1') {
    // Three admitted requests: a tool turn, a follow-up, and the same follow-up in a fresh session.
    const marker = `DEMO-${randomBytes(4).toString('hex')}`
    const recall = 'What was the fictional label in my previous message? If there was none, say NONE.'
    const answer = await sendChat(page, `My fictional label is ${marker}. Read the stored messages and summarize them.`)
    assert.equal(answer.execution.tool_used, true)
    assert.ok(answer.execution.rows_read > 0 && answer.execution.rows_read <= 4)
    assert.equal(answer.execution.model_requests, 2)
    assert.equal(answer.execution.commit, serving.commit)
    const follow = await sendChat(page, recall)
    assert.ok(follow.answer.toUpperCase().includes(marker.toUpperCase()), 'Follow-up recalled the synthetic label')
    assert.notEqual(follow.execution.trace_id, answer.execution.trace_id)
    assert.equal(follow.remaining, 3)
    await page.getByText('Inside this response').first().click()
    await page.getByText(/PostgreSQL tool/).first().waitFor()
    // Control errors before model admission; these tests use no additional inference.
    assert.equal((await context.request.post(`${demoUrl}/api/demo-chat`, { data: { message: 'csrf' } })).status(), 403)
    assert.equal((await context.request.post(`${demoUrl}/api/demo-chat`, { headers: { 'Sec-Fetch-Site': 'same-origin' }, data: { message: 'x'.repeat(601) } })).status(), 422)
    assert.equal((await context.request.post(`${demoUrl}/api/demo-chat`, { headers: { 'Sec-Fetch-Site': 'same-origin' }, data: { message: 'id probe', session_id: 'other-session' } })).status(), 422)

    const other = await browser.newContext()
    const otherPage = await other.newPage()
    await otherPage.goto(demoUrl)
    await otherPage.getByRole('button', { name: 'Try the demo', exact: true }).click()
    await otherPage.getByRole('heading', { name: 'A small Pydantic AI chat' }).waitFor()
    assert.equal(await otherPage.getByRole('list', { name: 'Conversation' }).getByRole('listitem').count(), 0)
    assert.equal((await (await other.request.get(`${demoUrl}/api/demo-chat`)).json()).remaining, 5)
    const isolated = await sendChat(otherPage, recall)
    assert.ok(!isolated.answer.toUpperCase().includes(marker.toUpperCase()), 'Other session cannot recall the label')
    assert.equal(isolated.remaining, 4)
    assert.equal((await (await context.request.get(`${demoUrl}/api/demo-chat`)).json()).remaining, 3)
    chatExecution = { toolTurn: answer.execution, followUp: follow.execution, otherSession: isolated.execution }
    await otherPage.getByRole('button', { name: 'Sign out', exact: true }).click()
    await other.close()
  } else {
    const chatStatus = await context.request.get(`${demoUrl}/api/demo-chat`)
    assert.equal(chatStatus.status(), 200)
    assert.equal((await chatStatus.json()).available, false, 'Omit VERIFY_CHAT only for an explicitly inactive chat')
  }

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
  console.log(JSON.stringify({ demoUrl, docsUrl, apiCommit: serving.commit, messages: data.length, chatExecution, result: 'passed' }))
} finally {
  await context.close()
  await browser.close()
}
