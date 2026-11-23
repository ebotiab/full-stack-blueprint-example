import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vitest/config'

// In development /api goes to the local API (`make dev` starts it on API_PORT, 8000 by default).
const apiTarget = process.env.API_PROXY ?? `http://127.0.0.1:${process.env.API_PORT ?? 8000}`

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: Number(process.env.WEB_PORT ?? 5173),
    proxy: { '/api': { target: apiTarget, changeOrigin: true } },
  },
  // Vercel gives the environment and the commit at build time; the visor reports errors with them
  // (src/telemetry.ts). Outside Vercel they are empty.
  define: {
    'import.meta.env.VITE_ENVIRONMENT': JSON.stringify(process.env.VERCEL_ENV ?? ''),
    'import.meta.env.VITE_COMMIT': JSON.stringify(process.env.VERCEL_GIT_COMMIT_SHA ?? ''),
  },
  // Unit tests (Vitest): plain logic next to the code, `*.test.ts`. Browser tests live in e2e/.
  test: { include: ['src/**/*.test.{ts,tsx}'], environment: 'node' },
})
