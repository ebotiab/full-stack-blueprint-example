// The visor's sign-in gate. It asks /api/auth/me who is signed in and shows the form until someone
// is. The session is an HttpOnly cookie that the browser sends with every /api request by itself:
// no token ever reaches this code, so a script injected into the page cannot steal it.
import { useEffect, useState, type FormEvent, type ReactNode } from 'react'

import { api } from './api/client'
import type { components } from './api/schema'
import { demoCredentials, publicDemo } from './demo'

type User = components['schemas']['User']

type State =
  | { status: 'loading' }
  | { status: 'error' }
  | { status: 'signed-out' }
  | { status: 'signed-in'; user: User }

const UNAVAILABLE = 'The API is not responding. Try again later.'

export function RequireSignIn({ children }: { children: ReactNode }) {
  const [state, setState] = useState<State>({ status: 'loading' })

  useEffect(() => {
    let active = true
    api
      .GET('/api/auth/me')
      .then(({ data, response }) => {
        if (!active) return
        if (data) setState({ status: 'signed-in', user: data })
        else setState(response.status === 401 ? { status: 'signed-out' } : { status: 'error' })
      })
      .catch(() => {
        if (active) setState({ status: 'error' })
      })
    return () => {
      active = false
    }
  }, [])

  function signOut() {
    api
      .POST('/api/auth/logout')
      .then(() => setState({ status: 'signed-out' }))
      .catch(() => setState({ status: 'signed-out' }))
  }

  if (state.status === 'signed-in') {
    return (
      <>
        <header>
          Signed in as {state.user.email}
          <button type="button" onClick={signOut}>
            Sign out
          </button>
        </header>
        {children}
      </>
    )
  }
  return (
    <main>
      <h1>{document.title}</h1>
      {state.status === 'loading' && (
        <p>
          {publicDemo ? 'Connecting… The free API may take about a minute to wake up.' : 'Loading…'}
        </p>
      )}
      {state.status === 'error' && (
        <>
          <p role="alert">{UNAVAILABLE}</p>
          <button type="button" onClick={() => window.location.reload()}>
            Retry connection
          </button>
        </>
      )}
      {state.status === 'signed-out' && (
        <SignInForm onSignedIn={(user) => setState({ status: 'signed-in', user })} />
      )}
    </main>
  )
}

// What the form says for each refusal of POST /api/auth/login.
const PROBLEMS: Record<number, string> = {
  401: 'Wrong email or password.',
  429: 'Too many attempts. Try again in a minute.',
}

function SignInForm({ onSignedIn }: { onSignedIn: (user: User) => void }) {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [problem, setProblem] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    signIn({ email, password })
  }

  function signIn(credentials: { email: string; password: string }) {
    setBusy(true)
    setProblem(null)
    api
      .POST('/api/auth/login', { body: credentials })
      .then(({ data, response }) => {
        setBusy(false)
        if (data) onSignedIn(data)
        else setProblem(PROBLEMS[response.status] ?? UNAVAILABLE)
      })
      .catch(() => {
        setBusy(false)
        setProblem(UNAVAILABLE)
      })
  }

  return (
    <form aria-label="Sign in" onSubmit={submit}>
      {publicDemo && (
        <section className="grid gap-3 rounded-lg border border-zinc-300 p-4 dark:border-zinc-700">
          <h2 className="font-semibold">Explore the live example</h2>
          <p className="text-sm">
            Fictitious data, a shared read-only visitor, and real session authentication.
          </p>
          <p className="text-sm">
            The free API may take about a minute to wake up after inactivity.
          </p>
          <button type="button" disabled={busy} onClick={() => signIn(demoCredentials)}>
            Try the demo
          </button>
        </section>
      )}
      <label>
        Email
        <input
          type="email"
          autoComplete="username"
          required
          value={email}
          onChange={(event) => setEmail(event.target.value)}
        />
      </label>
      <label>
        Password
        <input
          type="password"
          autoComplete="current-password"
          required
          value={password}
          onChange={(event) => setPassword(event.target.value)}
        />
      </label>
      {problem && <p role="alert">{problem}</p>}
      <button type="submit" disabled={busy}>
        Sign in
      </button>
    </form>
  )
}
