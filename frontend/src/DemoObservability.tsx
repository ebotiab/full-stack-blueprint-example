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
        see their own results. Sharing a trace requires a separate review.
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
