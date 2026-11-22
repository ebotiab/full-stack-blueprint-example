// The visor's sign-in gate. It asks /api/auth/me who is signed in and shows the form until someone
// is. The session is an HttpOnly cookie that the browser sends with every /api request by itself:
// no token ever reaches this code, so a script injected into the page cannot steal it.
import { useEffect, useState, type FormEvent, type ReactNode } from 'react'

import { api } from './api/client'
import type { components } from './api/schema'

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
      {state.status === 'loading' && <p>Loading…</p>}
      {state.status === 'error' && <p role="alert">{UNAVAILABLE}</p>}
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
    setBusy(true)
    api
      .POST('/api/auth/login', { body: { email, password } })
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
