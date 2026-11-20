import { Analytics } from '@vercel/analytics/react'
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'

import { App } from './App'
import './index.css'
import { startTelemetry } from './telemetry'

startTelemetry()

const root = document.getElementById('root')
if (!root) throw new Error('Missing #root element')

createRoot(root).render(
  <StrictMode>
    <App />
    {/* Vercel Web Analytics: no cookies; it only counts on Vercel and does nothing locally. */}
    <Analytics />
  </StrictMode>,
)
