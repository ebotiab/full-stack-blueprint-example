# Public demo operations

This repository owns the demo-specific changes. The template contains no demo domains or credentials.

| Component | Resource | Configuration |
| --- | --- | --- |
| Visor | Vercel `full-stack-blueprint-example` | GitHub `main`, root `frontend`, public production domain |
| API | Render `full-stack-blueprint-example-api` | Free, Frankfurt, Docker, `/api/healthz`, deploy after CI passes |
| Database | Neon `full-stack-blueprint-example` (`bold-salad-93466923`) | Free, PostgreSQL 18, Frankfurt, dedicated `blueprint_example` database |
| Traces | Logfire `ebotiab/full-stack-blueprint-example` | US region; server write token required, read token for verification |

Render's Blueprint automatically syncs `render.yaml` from `main`. `DATABASE_URL`, `LOGFIRE_TOKEN`
and `MY_PROJECT_ORIGIN_SECRET` belong only in the service's secret environment. Vercel's
`ORIGIN_SECRET` must match the API value. Only `VITE_PUBLIC_DEMO=true` enables the visitor button;
never put privileged credentials in a `VITE_` variable. The public demo sends Logfire telemetry from the API and Gateway only.

The public account is created idempotently at API startup with `MY_PROJECT_DEMO_ENABLED=true`.
It is not an administrator. The public deployment refuses mutations other than signing in,
ending the caller's own session and `POST /api/demo-chat`. The original `/api/agent` stays blocked.
Production enables the chat through its verified Groq Free route. Fresh installations default to inactive.
Login attempts share the PostgreSQL token bucket (burst of ten, one replenished per minute).
Do not store private data in this database or reuse this mode for another application.

## Verify a release

After merging on green, wait for both providers' deployments, then compare their Git SHAs with
the intended commit. A frontend-only change can leave Render on the last backend commit because
its root directory is `backend`.

```bash
VERIFY_CHAT=1 node scripts/verify-live-demo.mjs
cd backend
uv run my-project obs status --commit <API-commit> --wait 15
```

The browser script starts without saved authentication, follows the README link, signs in,
reads real API data, reloads to verify session and data persistence, checks isolation from an
anonymous browser, signs out, opens Swagger, and fails on browser/server errors. Optionally set
`EXPECTED_API_COMMIT` and `DEMO_SCREENSHOT` (a local image path). It never mocks requests or uses
a Vercel protection bypass. Keep browser state and traces containing cookies out of artifacts.

## Template updates

The real API address is a Copier answer (`api_public_url`), updated with Copier rather than by
editing `.copier-answers.yml`. Demo-only modules, migration, documentation and browser verification
script are local additions. Copier's three-way merge preserves changes in shared files.

Before merging a template update, run the template's `scripts/update-example.sh` on a clean,
isolated clone of this repository, then `make setup && make check`. Verify that the README's two
public links, both documentation proxy rules, visitor restrictions and `render.yaml` service name
remain present. Resolve any future conflicts explicitly; never overwrite with a fresh template copy.
The update to template HEAD `d9bddc8` was tested with all fourteen checks passing.

## Chat activation and cost (reviewed 2026-11-26)

The live API uses Pydantic AI 2.68.0, Logfire 5.6.0 and OpenAI Chat Completions.
The US route is `https://gateway-us.pydantic.dev/proxy/full-stack-blueprint-example-groq/chat/completions`.
The project-scoped key authorizes `project:gateway_proxy`. The model catalog and real tool turns
confirmed `openai/gpt-oss-20b`. The account owner confirmed Groq Free, a single Groq BYOK provider,
caching disabled on the key and **Include messages** off for the project. Initial native Gateway
traces showed Groq on attempt one for each call.

Groq publishes 30 requests/minute, 1,000/day, 8,000 tokens/minute and 200,000/day for this
model on Free. The provider response confirmed 1,000 requests/day and 8,000 tokens/minute.
Groq documents HTTP 429 at exhaustion. The verification stayed inside the upstream quota.
The free plan is quota-based. There is no paid fallback or prepaid-credit dependency.
The price estimate in a response is useful for comparing turns. Monetary inference cost on
the verified free account is $0. Paid inference would require a new budget design and explicit
approval. [Groq rate limits](https://console.groq.com/docs/rate-limits) ·
[Gateway BYOK](https://pydantic.dev/docs/logfire/manage/ai-gateway/byok-providers/)

### Reconnect or rotate

1. Keep `MY_PROJECT_DEMO_CHAT_ENABLED=false` while changing provider or capture settings.
   In the US organization `ebotiab`, select its dedicated endpoint and verify a single
   active Groq Free upstream with no paid fallback or retries. Confirm the model in its catalog.
   Personal supports three BYOK providers through the dashboard. The public provider and
   endpoint administration API returned 403 for this plan.
2. In **Gateway → Settings → Telemetry**, select `full-stack-blueprint-example` and turn off
   **Include messages**. Allow up to 60 seconds for propagation. Disable response caching
   on the inference key. Recheck the upstream account's retention terms.
   [Gateway retention](https://pydantic.dev/docs/logfire/manage/ai-gateway/data-retention/) ·
   [Groq data controls](https://console.groq.com/docs/your-data)
3. Place the project-only inference key in Render’s `PYDANTIC_AI_GATEWAY_API_KEY` and its route
   slug in `MY_PROJECT_DEMO_GATEWAY_ROUTE`. Render uses `LOGFIRE_TOKEN` for telemetry write.
   Keep `LOGFIRE_READ_TOKEN` in the operator environment. These three roles are independent.
4. After verifying the free upstream and privacy controls, enable the chat and verify the
   release with the commands above. The browser verifier spends three shared attempts and
   prints only execution metrics. Add `VERIFY_SESSION_CAP=1` to spend three additional attempts
   and verify that the sixth request in one session returns 429. Query its exact trace IDs in a short time window. Check span
   parents, served commit, rows, tokens, cost and both HTTP response codes. Expect one
   `my-project.demo-gateway` client span per model call and zero native `pydantic-ai-gateway`
   spans. Switch the chat off if the destination, billing or telemetry differs.

## Effective limits and isolation

The server accepts a message, never a conversation ID, user ID or history. `CurrentSession`
resolves the HttpOnly cookie, applies CSRF, and keys storage by the authenticated session row.
Two visitors using the same account have different rows. Logging out cascades deletion of only
that session's chat. The previous successful user/assistant pair (600/2,000 characters) supplies
context for 30 minutes. Expired content is excluded immediately and erased on the next admitted
attempt; expired session cleanup at login also removes it. No reasoning/tool transcript is saved.

Each request permits 600 characters, 512 generated tokens per model response, two model calls,
one typed tool call reading up to four rows of 240 characters, 8,000 reported total tokens,
30 seconds overall and 20 seconds per provider request. SDK and agent retries are zero.
No request waits in a queue. A PostgreSQL session advisory lock allows one active run across
processes. The reservation transaction commits before inference: five attempts/session,
20/day and 100/month (UTC). Failures, cancellation, crashes and restarts never refund attempts.
Re-login cannot reset global counters. An upstream request may finish after a client timeout;
its attempt remains reserved. This is safe only with the verified free upstream account;
a paid route would need a separate enforceable monetary budget.

A provider 429 opens a persistent circuit until the next UTC day. 401/402/403 block indefinitely
until the operator fixes the route and clears **only** `demo_chat_budget.blocked_until` for
`period='provider'`. Never clear turn counters as part of recovery. Other provider failures
consume the attempt and return a sanitized error without retries or fallback.

## Bounded observability and public explanation

In demo mode a custom OpenTelemetry sampler exports only admitted chat runs (at most 48 app
spans each) and up to 100 startup records/month, all reserved through PostgreSQL. Metrics are
disabled. Arbitrary API calls, rejected requests, logins and health probes do not cause ingest.
With pending-span records counted conservatively this is under 10,000 application records/month.
Each actual Gateway HTTP call gets a client span within the local allowance. Only the method,
US host, route, status and elapsed time are recorded there. Its parent model span carries usage
and reported cost. The outgoing W3C trace context keeps the IDs and clears the sampling bit.
This suppresses the hosted Gateway's separate span, which otherwise retains upstream response
headers even with **Include messages** off. No request/response headers are copied into the
client span. No visitor-facing Logfire
queries exist, so public traffic cannot run up query charges through the app.

Each successful response carries only its own duration, tool/row counts, request/token counts,
reported cost (null means unknown), trace ID and commit. The frontend renders these as text;
no HTML/Markdown supplied by the model is executed. Cost reported by Gateway can be a list-price
estimate for BYOK; it is not proof of a provider invoice. No prompts, answers, cookie values,
headers or user identifiers are intentionally included in spans. App content capture is always
off in demo mode; exception messages/stacktraces are scrubbed. Audit a real trace before sharing.

[Public Traces](https://pydantic.dev/docs/logfire/observe/public-traces/) can expose every span
and attribute of one trace. [Public Conversations](https://pydantic.dev/docs/logfire/observe/public-conversations/)
currently requires Early Access on Growth/Enterprise; no plan upgrade is needed for this demo's
safe execution summary. Project visibility `public` means within the organization, not anonymous.

The [public example](https://full-stack-blueprint-example.vercel.app/chat-trace.html) is a
manually reviewed static excerpt of a real production trace. It requires no account and executes
no scripts or Logfire queries. The native trace includes database role and host metadata, so the
public page contains only the selected timings, relationships and metrics. No visitor trace
is automatically published.

Personal retains source records for 30 days. The static example stays available independently.
To renew it, run the verifier, query only its synthetic trace IDs, review every span and update
the example and its commit in a PR. Test the deployed link in a fresh session. If sharing a
future native trace is appropriate, review **all** its attributes first, use its **Private**
control to create an expiring link and test that link anonymously. Expiration, revocation or
source-data retention can end access to a native link.

## Implementation checkpoint

The chat implementation passed all fourteen `make check` steps: 77 backend/PostgreSQL tests,
28 desktop/mobile browser tests and two frontend unit tests. `make coverage` reports 96% for
the chat module; the unexecuted lines are defensive impossible-row guards. The model tests are
offline doubles and do not validate a real Gateway route.

An isolated clone passed `scripts/update-example.sh HEAD` at template `65662c3` (v0.11.0).
To exercise actual regeneration too, `copier update --defaults --vcs-ref=HEAD --data description=…`
changed the description only in that disposable clone. Copier reported the expected README
conflict beside the local Live demo insertion: keep the entire local demo section and apply the
new generated description below it. All chat modules, guards, migration, proxy and deployment
settings survived. After resolving that text conflict, `make setup`, all fourteen checks and
another clean `scripts/update-example.sh HEAD` passed. No template change was needed, and this
does not promise conflict-free future upgrades.

A synthetic tool turn through the dedicated `full-stack-blueprint-example-groq` route
returned four PostgreSQL rows. A follow-up recalled a fictional label in its own session, and a
second session could not recall it. Before the client-side privacy change, Logfire showed the
US Gateway calling Groq once per model request. **Include messages** removed the bodies. Its
native spans still stored an upstream Cloudflare response cookie, so those traces must stay
private and expire under the 30-day Personal retention policy. The public example uses a fresh run after the change. The visitor's session cookie never went to the Gateway.

The US public API confirmed the Personal plan. Logfire received production startup records and
the served commit passed `obs status`. The account owner installed the project inference key in
Render. After the privacy change, the browser verifier completed both sessions. Logfire returned
eight spans for the tool turn, four for its follow-up and eight for the other session. The
HTTP client spans carried the route, host, method, status and agent correlation metadata. The
review found no cookies, credentials or conversation text in these traces.

Personal includes 10 million telemetry records per month across the organization with no
paid overage. Crossing the allowance restricts trace views and can eventually drop new
records. Retention is 30 days. The plan sets concurrent and daily query budgets for read
tokens. The visitor interface issues zero Logfire queries. Keep operator queries scoped to the
commit or synthetic trace and a short time window.
[Telemetry allowance and retention](https://pydantic.dev/docs/logfire/manage/logfire-costs/) ·
[Query limits](https://pydantic.dev/docs/logfire/reference/query-limits/)
