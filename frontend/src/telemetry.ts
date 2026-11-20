// Browser errors to Logfire, only in production builds that have a token (VITE_LOGFIRE_TOKEN, a
// restricted token of a Logfire *frontend application*, set in the Vercel project). Without a
// token nothing is loaded or sent, so development and tests never report anything.
// Options follow @pydantic/logfire-browser 0.35 (beta): re-read its docs when upgrading.

const token = import.meta.env.VITE_LOGFIRE_TOKEN as string | undefined
// The US region by default; EU projects use https://logfire-eu.pydantic.dev.
const baseUrl =
  (import.meta.env.VITE_LOGFIRE_BASE_URL as string | undefined) ?? 'https://logfire-us.pydantic.dev'

export function startTelemetry(): void {
  if (!import.meta.env.PROD || !token) return
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
