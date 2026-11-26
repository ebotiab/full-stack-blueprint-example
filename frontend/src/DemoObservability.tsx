export function DemoObservability() {
  return (
    <aside
      id="observability"
      aria-labelledby="observability-title"
      className="mx-auto max-w-2xl space-y-2 px-4 pb-10 text-sm text-zinc-600 dark:text-zinc-400"
    >
      <h2
        id="observability-title"
        className="text-lg font-semibold text-zinc-800 dark:text-zinc-200"
      >
        How the chat works
      </h2>
      <p>
        For an admitted question, the API reserves an attempt for your session. Pydantic AI sends
        the question and your previous exchange to the model through the US Logfire AI Gateway. If
        the model requests the read-only tool, the API reads up to four fictional PostgreSQL
        messages and sends the result through the same route for the answer.
      </p>
      <p>
        After a successful reply, open <strong>Inside this response</strong> for the duration, model
        calls, rows read, tokens, reported cost, trace ID and API commit from your turn. Visitors
        see their own results.
      </p>
      <p>
        <a
          href="https://logfire-us.pydantic.dev/public-trace/a52caeb8-f7f4-4851-a620-22e4e1c4c0f7?spanId=0a438f28431cf17a"
          className="underline underline-offset-2"
        >
          Explore the example trace in Logfire
        </a>{' '}
        to inspect both model calls, the tool and its database query. This reviewed example opens
        without an account. Its{' '}
        <a href="/chat-trace.html" className="underline underline-offset-2">
          timing summary
        </a>{' '}
        stays available after the public link expires.
      </p>
      <p>
        Each question can use 600 characters. A session gets five attempts. Visitors share 20
        attempts per UTC day and 100 per UTC month, including failures. The API admits one run at a
        time, with up to two model calls and one tool call. Follow-ups use the previous exchange for
        up to 30 minutes.
      </p>
    </aside>
  )
}
