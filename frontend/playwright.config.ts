import { defineConfig, devices } from '@playwright/test'

// End-to-end tests of the visor. They start Vite and answer /api themselves (page.route), so they
// need neither the API nor the database. E2E_PORT changes the port when 5199 is taken.
const port = Number(process.env.E2E_PORT ?? 5199)
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
