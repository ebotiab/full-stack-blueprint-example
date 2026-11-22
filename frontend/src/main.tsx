import { Analytics } from '@vercel/analytics/react'
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'

import { App } from './App'
import './index.css'
import { RequireSignIn } from './RequireSignIn'
import { startTelemetry } from './telemetry'

startTelemetry()

const root = document.getElementById('root')
if (!root) throw new Error('Missing #root element')

createRoot(root).render(
  <StrictMode>
    {/* Sign-in until someone is signed in, then the app (src/RequireSignIn.tsx). */}
    <RequireSignIn>
      <App />
    </RequireSignIn>
    {/* Vercel Web Analytics: no cookies; it only counts on Vercel and does nothing locally. */}
    <Analytics />
  </StrictMode>,
)
