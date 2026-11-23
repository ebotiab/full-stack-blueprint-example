import { once } from 'node:events'
import { createServer, type AddressInfo } from 'node:net'

import { defineConfig, devices } from '@playwright/test'

// End-to-end tests of the visor. They start Vite and answer /api themselves (page.route), so they
// need neither the API nor the database.

// A port nothing listens on: the system gives one to a server on port 0, closed right away.
async function freePort(): Promise<number> {
  const server = createServer().listen(0, '127.0.0.1')
  await once(server, 'listening')
  const { port } = server.address() as AddressInfo
  server.close()
  await once(server, 'close')
  return port
}

// Vite runs on a free port, so several projects or worktrees can run their checks at once.
// E2E_PORT chooses the port instead. Each worker loads this file again with the environment of
// the main process, so writing the port there keeps them all on the same server.
process.env.E2E_PORT ??= String(await freePort())
const port = Number(process.env.E2E_PORT)
const baseURL = `http://127.0.0.1:${port}`

export default defineConfig({
  testDir: './e2e',
  timeout: 30_000,
  fullyParallel: true,
  // Locally two workers: several projects or agents often test on the same machine at once.
  workers: process.env.CI ? undefined : Number(process.env.E2E_WORKERS ?? 2),
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? [['github'], ['list']] : 'list',
  use: { baseURL, trace: 'retain-on-failure', screenshot: 'only-on-failure' },
  webServer: {
    command: `npm run dev -- --port ${port} --strictPort --host 127.0.0.1`,
    url: baseURL,
    reuseExistingServer: false,
    timeout: 60_000,
  },
  projects: [
    { name: 'desktop', use: { ...devices['Desktop Chrome'] } },
    { name: 'mobile', use: { ...devices['Pixel 7'] } },
  ],
})
