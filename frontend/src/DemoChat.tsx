import { useEffect, useState } from 'react'

import { api } from './api/client'
import type { components } from './api/schema'

type Answer = components['schemas']['Answer']
type ChatStatus = components['schemas']['ChatStatus']

export function DemoChat() {
  const [status, setStatus] = useState<ChatStatus | null>(null)
  const [message, setMessage] = useState('')
  const [turns, setTurns] = useState<{ question: string; result: Answer }[]>([])
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    let active = true
    api
      .GET('/api/demo-chat')
      .then(({ data }) => {
        if (active) {
          if (data) setStatus(data)
          else setError('Chat status is unavailable. Please reload later.')
        }
      })
      .catch(() => {
        if (active) setError('The API is unavailable. Please reload later.')
      })
    return () => {
      active = false
    }
  }, [])

  async function send(event: React.SubmitEvent<HTMLFormElement>) {
    event.preventDefault()
    if (busy || !message.trim() || !status?.available) return
    const question = message.trim()
    setBusy(true)
    setError('')
    try {
      const { data, response } = await api.POST('/api/demo-chat', { body: { message: question } })
      if (data) {
        setTurns((old) => [...old, { question, result: data }])
        setMessage('')
        setStatus({
          available: data.remaining > 0,
          remaining: data.remaining,
          detail: data.remaining ? 'Ready.' : 'Session limit reached.',
        })
      } else {
        const messages: Record<number, string> = {
          401: 'Your session ended. Reload and sign in again.',
          403: 'This request was refused. Reload the demo and try again.',
          422: 'The question or model response exceeded the demo limits. Please keep it short.',
          429: 'The demo is busy or its shared/session quota is exhausted. Please try later.',
          502: 'The Gateway or model is unavailable or out of quota. No fallback was used.',
          503: 'Chat has not been activated or its Gateway configuration is missing.',
          504: 'The model took too long. No automatic retry was made.',
        }
        setError(messages[response.status] ?? 'Chat failed. Please try later.')
      }
    } catch {
      setError('Connection lost. The attempt may have used quota; it was not retried.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <section
      aria-labelledby="chat-title"
      className="mt-10 border-t border-zinc-300 pt-6 dark:border-zinc-700"
    >
      <h2 id="chat-title" className="text-xl font-semibold">
        A small Pydantic AI chat
      </h2>
      <p className="my-3 text-sm text-zinc-500">
        Ask about the fictional messages above. Only your previous exchange is remembered, for up to
        30 minutes. Please do not enter personal information.
      </p>
      <output className="mb-3 block text-sm">
        {busy
          ? 'Thinking…'
          : status
            ? `${status.detail} ${status.remaining} attempts left in this session.`
            : 'Checking chat availability…'}
      </output>
      <div className="mb-4 flex flex-wrap gap-2" aria-label="Suggested questions">
        {[
          'Read the stored messages and summarize them.',
          'Which message mentions the API?',
          'Explain how your read-only tool works.',
        ].map((text) => (
          <button
            key={text}
            type="button"
            disabled={busy || !status?.available}
            onClick={() => setMessage(text)}
          >
            {text}
          </button>
        ))}
      </div>
      <ol aria-label="Conversation" className="space-y-4" aria-live="polite">
        {turns.map(({ question, result }, index) => (
          <li key={index} className="rounded-lg bg-zinc-100 p-4 dark:bg-zinc-900">
            <p className="font-medium">You: {question}</p>
            <p className="mt-2 whitespace-pre-wrap">Assistant: {result.answer}</p>
            <details className="mt-3 text-sm text-zinc-500">
              <summary className="cursor-pointer">Inside this response</summary>
              <p>
                API → Pydantic AI → US Gateway → model
                {result.execution.tool_used
                  ? ` → PostgreSQL tool (${result.execution.rows_read} rows) → US Gateway → model`
                  : ''}
              </p>
              <p>
                {result.execution.duration_ms} ms · {result.execution.model_requests} model calls ·{' '}
                {result.execution.input_tokens} input / {result.execution.output_tokens} output
                tokens
              </p>
              <p>
                Gateway reported cost:{' '}
                {result.execution.cost_usd === null
                  ? 'unavailable'
                  : `$${result.execution.cost_usd}`}{' '}
                USD. A free provider account may bill $0 even when the Gateway reports a list-price
                estimate.
              </p>
              <p className="break-all">
                Model: {result.execution.model}. Trace: {result.execution.trace_id}. API commit:{' '}
                {result.execution.commit ?? 'local'}.
              </p>
            </details>
          </li>
        ))}
      </ol>
      <form onSubmit={send} className="mt-4 w-full max-w-none">
        <label>
          Your message
          <input
            name="message"
            value={message}
            onChange={(event) => setMessage(event.target.value)}
            maxLength={600}
            required
            disabled={busy || !status?.available}
            autoComplete="off"
          />
        </label>
        <button disabled={busy || !status?.available || !message.trim()}>
          {busy ? 'Thinking…' : 'Send'}
        </button>
      </form>
      {error && (
        <p role="alert" className="mt-3">
          {error}
        </p>
      )}
    </section>
  )
}
