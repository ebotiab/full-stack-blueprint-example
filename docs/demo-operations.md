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
never put privileged credentials in a `VITE_` variable. Browser Logfire, when configured, uses
only a restricted frontend application token with the production origin allowed.

The public account is created idempotently at API startup with `MY_PROJECT_DEMO_ENABLED=true`.
It is not an administrator. The public deployment refuses mutations other than signing in,
ending the caller's own session and `POST /api/demo-chat`. The original `/api/agent` stays blocked.
The chat is shipped **inactive** until its free Gateway route and telemetry are verified.
Login attempts share the PostgreSQL token bucket (burst of ten, one replenished per minute).
Do not store private data in this database or reuse this mode for another application.

## Verify a release

After merging on green, wait for both providers' deployments, then compare their Git SHAs with
the intended commit. A frontend-only change can leave Render on the last backend commit because
its root directory is `backend`.

```bash
node scripts/verify-live-demo.mjs
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

Pydantic AI 2.68.0 and Logfire 5.6.0 are already installed. No extra AI dependency or hosting
service is needed. The candidate is Groq Free `openai/gpt-oss-20b` through a **dedicated BYOK
route** in Logfire Gateway US. It is not a direct Groq call. The route is still unverified in
this account; do not claim live inference until the activation checks below pass.

- [Groq's official limits](https://console.groq.com/docs/rate-limits) list 30 requests/minute,
  1,000/day, 8,000 tokens/minute and 200,000/day for this model on Free. Excess returns 429.
  This is a quota-based free plan, not expiring prepaid credits; account limits and continued
  model availability still need verification. Do not upgrade the upstream account.
- [Gateway BYOK](https://pydantic.dev/docs/logfire/manage/ai-gateway/byok-providers/) is available
  on Personal (up to three providers). The upstream provider bills usage. Built-in Gateway
  providers instead draw prepaid balance; promotional credits are temporary and are not a
  permanent free tier. Their activation can request a payment method or auto-recharge: do not enable either.
- [Gateway spending limits](https://pydantic.dev/docs/logfire/manage/ai-gateway/spending-policies/)
  accept whole USD; zero blocks requests. They do not establish a cents-level hard cap.
  Pydantic AI's token/cost checks occur after responses and cannot establish one either.
- The [Groq paid list price](https://console.groq.com/docs/models) is $0.075/M input tokens and
  $0.30/M output tokens. A typical two-call turn with 2,000 total input and 512 total output
  tokens would be about $0.000304. This is an estimate, **not an approved budget or enforced
  paid limit**. Paid use is disabled; a separate reviewed reservation budget (proposed $0.05/month)
  and explicit owner approval would be required before enabling any paid route.
- Render Free, Neon Free and the existing Vercel deployment are reused. No plans, credits,
  auto-recharge or new paid services are enabled. Logfire's free observability allowance is
  separate from model billing; inspect the actual project plan and ingest/query limits.

Activation, only for this example:

1. Use the existing project `ebotiab/full-stack-blueprint-example` in US. With authorized
   Gateway management access, inspect current providers, plan, balance, credits/expiry and
   key/project limits. Preserve every other project's configuration.
2. If needed, connect an independently verified **Free** Groq account as a dedicated supported
   BYOK provider and a route with only that provider, no fallback or Gateway retry. Verify
   `openai/gpt-oss-20b` is served by the route. Never silently select a paid built-in provider.
3. Enable Gateway telemetry for this project, but disable request/response content capture
   there too. Application `include_content=False` does not change Gateway capture. Apply
   project ingest/query caps below the included allowances before opening public traffic.
4. Create/reuse a project-only inference key with minimum permissions. Store its value only in
   Render's `PYDANTIC_AI_GATEWAY_API_KEY`. Store the route slug in `MY_PROJECT_DEMO_GATEWAY_ROUTE`.
   The application pins the US base `https://gateway-us.pydantic.dev/proxy`, OpenAI chat protocol,
   and model; the effective URL is `/proxy/<verified-route>/chat/completions`.
5. Keep `MY_PROJECT_DEMO_CHAT_ENABLED=false` until the route's cost and capture controls are
   verified. Then enable it, test one synthetic turn and its continuation, and query the new
   trace using `LOGFIRE_READ_TOKEN` from the operator environment. Never install that read token
   in Vercel, frontend artifacts or a public query API. No OAuth wizard is required for valid keys.
6. Run the browser verifier with `VERIFY_CHAT=1`, then `obs status` for the served API commit.
   Record the verified route, account quotas, measured tokens/cost and reviewed trace link here,
   and remove the README's inactive notice only after that verification.

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
these controls are not advertised as a paid dollar cap.

A provider 429 opens a persistent circuit until the next UTC day. 401/402/403 block indefinitely
until the operator fixes the route and clears **only** `demo_chat_budget.blocked_until` for
`period='provider'`. Never clear turn counters as part of recovery. Other provider failures
consume the attempt and return a sanitized error without retries or fallback.

## Bounded observability and public explanation

In demo mode a custom OpenTelemetry sampler exports only admitted chat runs (at most 48 app
spans each) and up to 100 startup records/month, all reserved through PostgreSQL. Metrics are
disabled. Arbitrary API calls, rejected requests, logins and health probes do not cause ingest.
With pending-span records counted conservatively this is under 10,000 application records/month.
Gateway telemetry is separate: at most 200 successful model calls/month are initiated by this
application, but its own retry/ingest limits must still be verified. No visitor-facing Logfire
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

After the real synthetic verification, review the **entire** trace, then create a public trace
link under its Private/share control, set an expiry and test it in a clean browser. Do not share
visitor traces automatically. Links can stop working at expiration, revocation or source-data
retention; even “Never” does not extend retention. To renew: generate another synthetic run,
review it, create a new expiring link, test anonymously and replace the documented link.
No public trace has yet been verified for this chat; the safe in-page explanation is available.

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

The operator confirmed that the replacement Gateway-capable key was saved for **future cloud
sessions**. This running environment still has only the earlier `LOGFIRE_READ_TOKEN`: Logfire
queries and `obs status` work, but the public management API returns 401. Continue activation
in a session created with the updated environment. Use the existing key through its secret
binding; do not repeat OAuth setup or put its value in chat. Public Gateway management schema:
`https://logfire-us.pydantic.dev/api/openapi.json`; official API base:
`https://api-us.pydantic.dev/api/v1/`. A management key is not automatically the project-only
inference key that should be installed in Render.
