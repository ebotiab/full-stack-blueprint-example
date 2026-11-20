// Browser errors to Logfire, only in production builds that have the two values Logfire generates
// for a *frontend application* (Frontend → Applications), set in the Vercel project: its restricted
// token (VITE_LOGFIRE_TOKEN) and the URL of the project's region (VITE_LOGFIRE_BASE_URL,
// https://logfire-eu.pydantic.dev or https://logfire-us.pydantic.dev). Without a token nothing is
// loaded or sent, so development and tests never report anything.
// Options follow @pydantic/logfire-browser 0.35 (beta): re-read its docs when upgrading.

const token = import.meta.env.VITE_LOGFIRE_TOKEN as string | undefined
const baseUrl = import.meta.env.VITE_LOGFIRE_BASE_URL as string | undefined

export function startTelemetry(): void {
  if (!import.meta.env.PROD || !token) return
  if (!baseUrl) {
    // No guessed region: the other region would reject the token and nothing would say so.
    console.error('VITE_LOGFIRE_TOKEN needs VITE_LOGFIRE_BASE_URL: browser telemetry is off.')
    return
  }
  // A separate chunk: visitors only download the SDK when telemetry is on.
  void import('@pydantic/logfire-browser').then(({ configureFrontend }) => {
    configureFrontend({
      baseUrl,
      token,
      // Only traces with an error, no Web Vitals, no page-load spans.
      profile: 'errors',
      // No automatic fetch/click spans: errors are what matters here.
      autoInstrumentations: false,
      // Uncaught errors and unhandled rejections are reported.
      captureGlobalErrors: true,
      // Without a fingerprint an error arrives but opens no issue in Logfire's error tracking.
      errorFingerprinting: true,
      serviceVersion: import.meta.env.VITE_COMMIT || undefined,
      resourceAttributes: {
        'deployment.environment.name': import.meta.env.VITE_ENVIRONMENT || 'local',
      },
    })
  })
}
