// Typed client for the API. `schema.d.ts` is generated from backend/openapi.json (`make types`):
// never edit it by hand, and regenerate it whenever an API route or model changes.
import createClient from 'openapi-fetch'

import type { components, paths } from './schema'

// Same origin everywhere: in development Vite proxies /api to the local API, and in production
// Vercel routes /api to the API (vercel.json). No CORS, no API URL in the bundle.
export const api = createClient<paths>()

export type Message = components['schemas']['Message']
