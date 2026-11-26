import { useEffect, useState } from 'react'

import { api, type Message } from './api/client'
import { formatDate } from './lib/format'
import { publicDemo } from './demo'
import { DemoChat } from './DemoChat'

type State = { status: 'loading' } | { status: 'error' } | { status: 'ready'; messages: Message[] }

export function App() {
  const [state, setState] = useState<State>({ status: 'loading' })

  useEffect(() => {
    let active = true
    api
      .GET('/api/messages')
      .then(({ data }) => {
        if (active) setState(data ? { status: 'ready', messages: data } : { status: 'error' })
      })
      .catch(() => {
        if (active) setState({ status: 'error' })
      })
    return () => {
      active = false
    }
  }, [])

  return (
    <main>
      <h1>{document.title}</h1>
      {publicDemo && (
        <p className="mb-6 text-sm text-zinc-500">
          These example messages are stored in PostgreSQL and loaded through the authenticated API.
          The chat can read this fictional data. Other visitor actions remain read-only.
        </p>
      )}
      {state.status === 'loading' && <p>Loading…</p>}
      {state.status === 'error' && <p role="alert">The API is not responding. Try again later.</p>}
      {state.status === 'ready' && (
        <ul aria-label="Messages">
          {state.messages.map((message) => (
            <li key={message.id}>
              {message.text}{' '}
              <time dateTime={message.created_at}>{formatDate(message.created_at)}</time>
            </li>
          ))}
        </ul>
      )}
      {publicDemo && <DemoChat />}
    </main>
  )
}
