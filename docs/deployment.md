# Production deployment

## Deployment target and what this repository verifies

The documented production target is a Next.js frontend on Vercel, a FastAPI API
on Render, and PostgreSQL on Neon. A separate Render background worker is
needed only for enabled polling jobs. The API process never starts that worker.
Redis is used by local Compose only; it is not required by the production
processes.

These are deployment instructions, not proof of currently provisioned services.
This repository contains no `render.yaml`, `vercel.json`, or app deployment
workflow. Provider service names, domains, deployment branches, active
environment values, Neon project/connection details, Render health-check
settings, and automatic deploy-on-push configuration must be confirmed in the
respective dashboards. Do not copy example values from old environment files
into production.

## Frontend (Vercel)

Set the Vercel project root directory to `frontend`. The app uses Node.js 20.9
or newer, `npm ci`, and `npm run build`.

For production, configure:

- `API_PROXY_TARGET` — the Render API origin (scheme and host only, no path).
  Next.js rewrites `/api/:path*` to that origin. This is a server-side Next.js
  setting, not a `NEXT_PUBLIC_*` value. Set it in the Vercel deployment
  environment; without it, the same-origin API rewrite is absent.
- `NEXT_PUBLIC_API_URL` — leave unset or set to `same-origin`. The browser then
  requests `/api/...` from the Vercel origin and the rewrite forwards it to
  Render. Do not configure a direct Render URL for the production browser.

The frontend API client includes credentials and adds
`X-FlowPilot-Request: 1` to unsafe requests. The proxy keeps the browser-facing
request same-origin; do not rely on third-party cookie behavior between Vercel
and Render.

Optional frontend settings:

- `NEXT_PUBLIC_SITE_URL` — the known public marketing origin (scheme and host,
  no path), used for canonical/Open Graph URLs and sitemap/robots output.
  Leave unset until the real public origin is known; localhost and common
  preview hosts are not accepted as production metadata origins.
- `NEXT_PUBLIC_GOOGLE_CLIENT_ID` — public OAuth Web client ID for the Google
  sign-in button. It must match the API client ID. Never put the OAuth client
  secret in frontend configuration.

For local `next dev`, set `NEXT_PUBLIC_API_URL` to the local API origin and
leave `API_PROXY_TARGET` unset.

## API (Render web service)

The following are recommended Render service settings; they are not encoded in
a Render manifest in this repository:

- Root directory: repository root.
- Build command: `pip install ./backend` (Python 3.12 or newer).
- Pre-deploy command: `cd backend && alembic upgrade head`.
- Start command:

```bash
cd backend && uvicorn app.main:app --host 0.0.0.0 --port "$PORT"
```

Render supplies `PORT`. The production package includes Uvicorn and Alembic;
the `dev` extra is for CI and local checks, not required for the API release.
Migrations are a separate step, not part of application startup. Configure the
pre-deploy command in Render if desired, serialize schema-changing deploys, and
do not run migrations in request handlers.

### Required production settings

`ENVIRONMENT`, `SECRET_KEY`, `DATABASE_URL`, and `CORS_ORIGINS` must be valid
for every production process using the shared settings, including a worker.
The application rejects the insecure example secret, secrets shorter than 32
characters, the built-in local database default, SQLite production databases,
and missing or `*` CORS origins, origins containing `localhost` or
`127.0.0.1`, and origins that do not use HTTPS.

- `ENVIRONMENT=production`.
- `SECRET_KEY` — unique high-entropy signing secret of at least 32 characters.
- `DATABASE_URL` — set the Neon PostgreSQL connection string on the API and
  any worker. Use Neon's TLS-enabled connection settings (normally
  `sslmode=require`). The application normalizes common PostgreSQL URL schemes
  to the installed psycopg 3 driver, but it does not verify that the host is
  Neon or enforce an SSL query option.
- `CORS_ORIGINS` — comma-separated production frontend origins, using HTTPS
  and no path. Do not use `*`, localhost, or loopback origins. This setting is
  still required by production startup when browser traffic uses the Vercel
  same-origin proxy; it also governs credentialed direct browser requests to
  the API. The API CORS middleware allows credentials for configured origins.
- `PORT` — supplied by Render and consumed by the start command; it is not a
  FlowPilot secret.

### Browser session, proxy, and CSRF

The API sets the JWT as the host-only `flowpilot_session` cookie. It is
`HttpOnly`, has no `Domain` attribute, and is `Secure` in production.
`SESSION_COOKIE_SAMESITE` is optional and accepts `lax`, `strict`, or `none`:
the production default is `None`, while non-production defaults to `Lax`.
`None` is allowed only in production and requires the secure cookie. With the
recommended Vercel same-origin rewrite, `Lax` can also be used if the
deployment's site arrangement allows it.

Cookie-authenticated `POST`, `PUT`, `PATCH`, and `DELETE` requests must include
`X-FlowPilot-Request: 1`; the frontend client supplies it automatically. This
header is a CSRF defense, not a secret. Bearer-token clients are also supported.
Keep `CORS_ORIGINS` explicit for any clients that call the API cross-origin;
CORS configuration does not make third-party cookies reliable in browsers.

### Health checks

- `GET /health` is liveness only and does not check PostgreSQL.
- `GET /health/ready` executes a database check and returns 503 if the database
  is unavailable, without returning connection details.

If configuring a Render web-service health check, use `/health/ready` when the
check should include database readiness. The repository has no Render manifest,
so the active dashboard health-check path cannot be verified.

### Optional API settings

These settings are feature-specific; missing optional credentials do not
prevent production startup. A feature that needs an unconfigured provider may
report that provider as unavailable when called.

- **AI:** `AI_PROVIDER` selects `openai` or `groq` and defaults to `openai`.
  Configure `OPENAI_API_KEY` or `GROQ_API_KEY` for the selected provider.
  `OPENAI_MODEL` and `GROQ_MODEL` have defaults. Supplying a key for the
  non-selected provider does not configure the selected one.
- **Human-decision calls:** `TYPESAFE_API_KEY` is optional and is needed only
  for the TypeSafe human-escalation decision integration.
- **Knowledge embeddings:** disabled by default. Set
  `EMBEDDING_PROVIDER_ENABLED=true` and configure `OPENAI_API_KEY` to request
  embeddings; otherwise lexical retrieval remains available. The embedding
  model defaults to `text-embedding-3-small`.
- **Outbound email and account links:** `RESEND_API_KEY` and
  `EMAIL_FROM_ADDRESS` are needed for email delivery; the sender address must
  be on a Resend-verified domain. `EMAIL_FROM_NAME` is optional.
  `APP_BASE_URL` must be set to the frontend origin for invitation, email
  verification, and password-reset links to be sent; those link emails are
  skipped when the origin or sender is not configured.
- **Google sign-in:** configure `GOOGLE_OAUTH_CLIENT_ID` and
  `GOOGLE_OAUTH_CLIENT_SECRET` on the API and the matching
  `NEXT_PUBLIC_GOOGLE_CLIENT_ID` on Vercel. Register the frontend JavaScript
  origin in Google Cloud Console. The API exchanges GIS popup authorization
  codes using `redirect_uri=postmessage`. Missing API credentials make only
  the Google sign-in route unavailable.
- **Inbound Resend mail:** see [Inbound email](#inbound-email). Outbound
  sending does not require the inbound signing secret or domain.
- **Generic outgoing webhooks:** webhook endpoints are configured in
  FlowPilot; `WEBHOOK_WORKER_ENABLED=true` is required on a worker for queued
  deliveries. Slack Incoming Webhook formatting is not a native Slack OAuth
  integration.
- **Company-prospect discovery import:** the server-side
  `PROSPECT_DISCOVERY_APPROVED_IMPORT_SOURCE` setting is unset by default.
  Import remains blocked until an approved source label is explicitly
  configured. The Discovery Workspace import control remains disabled.
- **Public website capture:** an owner/admin must enable capture in the
  organization settings. PostgreSQL-backed attempt limits are shared across
  API processes; `WEBSITE_CAPTURE_RATE_LIMIT_MAX` and
  `WEBSITE_CAPTURE_RATE_LIMIT_WINDOW_SECONDS` default to 5 and 60.
  Migration `045_website_capture_attempts` creates the shared attempt table.
  `WEBSITE_CAPTURE_DAILY_ENQUIRY_CAP` defaults to 100 per organization per UTC
  day and can be tuned.
- **Public contact and prospect-discovery rate limits:** the contact limit
  settings and `PROSPECT_DISCOVERY_RATE_LIMIT_MAX`,
  `PROSPECT_DISCOVERY_RESULT_LIMIT`, and
  `PROSPECT_DISCOVERY_USAGE_WINDOW_SECONDS` use in-process counters and are
  not shared across API replicas. Discovery page-size and cursor settings are
  bounds, not distributed rate limits. `REDIS_URL` is not used as a production
  rate-limit store or job queue.

### Government company discovery (optional)

This integration is disabled by default. Do not enable it for customer use until you have written confirmation from the data provider that your intended commercial use and expected API quota are permitted. An API key alone is not permission for commercial use.

After that approval, add these variables to the **API web service** environment in Render (never to Vercel or a `NEXT_PUBLIC_*` variable):

- `ROC_DATA_GOV_IN_API_KEY` — the server-side API key issued by data.gov.in; keep it secret
- `ROC_DATA_GOV_IN_PROVIDER_ENABLED=true`
- `ROC_DATA_GOV_IN_REQUEST_TIMEOUT_SECONDS=10` (optional; allowed range is 1–30)
- `ROC_DATA_GOV_IN_MAX_PAGE_SIZE=100` (optional; allowed range is 1–100)
- `ROC_DATA_GOV_IN_MAX_OFFSET=100000` (optional; allowed range is 0–1000000)

Save the environment changes and restart or redeploy the API service. The authenticated prospect-discovery page reads availability from the API at runtime; once the API has both the key and explicit enable flag, its government search fields become active. If it remains unavailable, confirm both variables are set on the API service and inspect the API service's configuration without printing or sharing the key. The endpoint is read-only and results are not saved to the CRM.

## Worker (Render background worker)

Configure a separate Render Background Worker from the same repository. Use
the production backend dependencies and the database and production settings
required by the API. At least one worker flag must be enabled; otherwise the
process exits successfully immediately. Do not expose a public HTTP service or
run `uvicorn` in this service.

Start command:

```bash
cd backend && python -m app.worker
```

The `python -m app.worker` process starts only the enabled loops. Each flag is
optional and defaults to `false`:

- `FOLLOW_UP_WORKER_ENABLED=true` sends due follow-up email. Configure Resend
  and a verified sender as described above.
- `SALES_AGENT_AUTO_START_WORKER_ENABLED=true` starts the Sales Agent for
  eligible website enquiries. Website capture and a default Sales Agent must
  also be enabled in the organization settings.
- `WORKFLOW_WORKER_ENABLED=true` runs enabled workflow rules.
- `WEBHOOK_WORKER_ENABLED=true` delivers queued outgoing webhooks.
- `FORECAST_SNAPSHOT_WORKER_ENABLED=true` polls for daily forecast snapshots.
  The poll interval defaults to 300 seconds and batch size to 100. Migration
  `038_forecast_snapshots` must be applied. The GitHub Actions one-off schedule
  below can capture these snapshots instead.

Each loop polls rather than using a cron trigger. Optional
`*_POLL_INTERVAL_SECONDS` and `*_BATCH_SIZE` settings tune its work:
follow-up, Sales Agent auto-start, and workflow loops default to 30 seconds and
10 items; webhooks default to 15 seconds and 20 items; forecast snapshots
default to 300 seconds and 100 items. Enabled loops share this process.

Leave worker flags false on the API service; the API does not start these
loops. The worker uses database-backed polling, not Celery, Redis, or another
queue. Do not enable a loop until its provider credentials and business-level
settings are ready.

## CI/CD and deployment health checks

The [CI workflow](../.github/workflows/ci.yml) runs on pull requests and pushes
to `main`. It checks backend Ruff, mypy, and pytest; runs the isolated
PostgreSQL integration tests; checks frontend ESLint, TypeScript, unit tests,
and production build; and runs browser E2E tests. The PostgreSQL service
`pg_isready` checks are CI infrastructure health checks, not production
deployment checks.

There is no Vercel/Render deploy job in this repository. CI success does not
prove that a provider deployment occurred or that a deployed service is
healthy. Whether Vercel or Render deploys automatically from a branch is an
external project setting and must be verified in that provider's dashboard.
The API health endpoints above can be used for a post-deploy check; no
post-deploy smoke check is defined in the repository workflows.

## Forecast snapshots (GitHub Actions)

[The forecast-snapshots workflow](../.github/workflows/forecast-snapshots.yml)
defines an optional scheduled runner for daily forecast snapshots. It is not
a deployment workflow. It runs:

```bash
cd backend && python -m app.worker.forecast_snapshot_once
```

The runner captures every organization that has no snapshot for today (UTC), in batches of `FORECAST_SNAPSHOT_WORKER_BATCH_SIZE` (default 100), prints one line of counts and exits: 0 when the lookup and every capture succeeded, 1 otherwise. It does not read `FORECAST_SNAPSHOT_WORKER_ENABLED`. Capture is idempotent per organization and UTC day, so repeated, overlapping or manual runs never add a second snapshot. A failed organization is normally left for the next run; in a long run it can be tried again once its five-minute retry delay has passed. If the organization lookup, or the retry check after a batch, fails, the run exits 1 and its summary may not include that batch's counts.

The workflow file schedules runs at 00:17, 06:17, 12:17 and 18:17 UTC and
supports manual dispatch. The first run captures the day; later runs catch up
after a delayed or failed run and otherwise do nothing when all organizations
have today's snapshot. It has no push or pull-request trigger, gates the job to
`main`, has read-only repository permissions, a 10-minute timeout, and does
not cancel an in-progress run.

To configure the workflow, create the GitHub Actions environment named
`Production` (matching the workflow), then add:

- Environment secrets: `DATABASE_URL` for the Neon database already migrated
  for the application, and a unique high-entropy `SECRET_KEY` of at least 32
  characters for this job. The one-off runner does not sign tokens; do not
  reuse the API service's `SECRET_KEY`.
- Environment variable (not a secret): `CORS_ORIGINS`, set to the HTTPS
  production frontend origin. The production settings validator requires it
  even though this job does not serve HTTP.

The workflow's preflight step reports missing setting names, never values.
Do not add steps that print environment variables or enable debug logging.
The YAML references these environment secrets and variable, but their presence,
environment protection rules, and the workflow's enabled state must be verified
in GitHub; they are not stored in this repository.

Treat workflow logs as visible to repository users (and public if the repository
is public). The runner reports aggregate counts only, without organization
identifiers, SQL parameters, connection details, exception messages, or
tracebacks. Errors inside the runner are reported by class; settings validation
also redacts supplied values. To check a run, open Actions → Forecast snapshots
and read the last line of "Capture forecast snapshots":

- `status=complete … failed=0 lookup_failed=false` — every organization has today's snapshot.
- `status=failed` with `failed=N` — N captures failed; the next run retries them.
- `status=failed … lookup_failed=true` — organization lookup or retry lookup
  failed. `status=error error=<Class>` indicates a runner setup/execution error.
  A `ValidationError` indicates invalid settings. Check the relevant
  configuration and confirm migration `038_forecast_snapshots` is applied.

Scheduled runs can be delayed or skipped; later runs are intended to catch up.
GitHub may disable scheduled workflows in inactive public repositories, so
verify that the workflow remains enabled in Actions. GitHub notification
delivery depends on repository-user notification settings.

The Render worker can still be needed for follow-up email, Sales Agent
auto-start, workflow rules, or outgoing webhooks even if GitHub Actions handles
forecast snapshots. The worker's snapshot loop and the one-off runner are
idempotent and can overlap safely. Before disabling a worker loop or removing
the service, check all enabled worker flags and verify scheduled captures if
they are intended to replace that loop.

Forecast snapshots are unique per organization and UTC day. To check how many
organizations still lack today's monthly snapshot, run this read-only query
against the production database using an approved database client:

```sql
SELECT count(*) AS missing
FROM organizations o
LEFT JOIN forecast_snapshots s
  ON s.organization_id = o.id
 AND s.snapshot_date = (now() AT TIME ZONE 'UTC')::date
 AND s.granularity = 'month'
WHERE s.id IS NULL;
```

## Migrations

Configure `cd backend && alembic upgrade head` as the Render pre-deploy
command if migrations should run during deployment. The repository does not
encode or confirm this provider setting. Run schema changes serially; do not
start concurrent deploys that both apply migrations. Do not run migrations
from API startup or a request handler.

### Follow-up sequence rollout

Migration `049_lead_follow_up_sequence` is the expand step. It adds a nullable
sequence, deterministically backfills existing follow-ups by `created_at` and
`id`, and adds the check and unique constraints. It intentionally has no
default. On PostgreSQL, a temporary `BEFORE INSERT` trigger assigns a sequence
when an older API process omits the field; the trigger locks the tenant-scoped
parent lead before reading the maximum. This lets old and new processes safely
write during the expand phase. Existing timestamp ties cannot reveal their
true historical insertion order.

Roll out this schema change in stages:

1. Run `cd backend && alembic upgrade 049_lead_follow_up_sequence` while the
   old API version is still deployed. Do not use `upgrade head` yet.
2. Deploy the sequence-aware API release. Its repository allocates a unique
   per-lead sequence using the same parent-lead lock as the compatibility
   trigger. The nullable expanded schema and trigger support mixed versions.
3. After all old API instances and workers that can create follow-ups are
   stopped or drained, run `cd backend && alembic upgrade head`. Migration
   `050_follow_up_sequence` deterministically numbers any
   rollout-era null rows, removes the compatibility trigger, and enforces
   `NOT NULL`. It takes an exclusive PostgreSQL table lock while backfilling,
   so schedule a brief pause for follow-up traffic. For tied timestamps, known
   sequences are preserved where possible; null legacy rows use a deterministic
   order because their true insertion order cannot be recovered. The sequence
   is authoritative after this contract step.
4. Subsequent releases can use the normal `alembic upgrade head` pre-deploy
   command.

To roll back to application code that predates sequence allocation, stop the
sequence-aware API and workers first, then run
`cd backend && alembic downgrade 048_company_contact_foundation` before
deploying the old code. This removes the internal sequence data and both
sequence migrations; do not downgrade while sequence-aware processes are
serving traffic. Downgrades remain reviewed, manual operations.

Check the Render deploy record to confirm whether a migration step ran and
succeeded before serving the new release. Roll back application code only when
it remains compatible with the current schema. Alembic downgrades are manual,
reviewed operations, not routine deploy steps.

## Inbound email

The API route `POST /api/v1/webhooks/resend/inbound` is implemented; receiving
mail in production requires external Resend setup. Configure:

- `RESEND_WEBHOOK_SECRET` on the API service, set to the Resend webhook signing secret
- `RESEND_INBOUND_DOMAIN` set on the API service to the domain whose recipient local-part equals an organization slug, such as `acme@inbound.example.com`
- `RESEND_API_KEY` set so metadata-only `email.received` events can fetch the body via Resend Receiving (`GET /emails/receiving/{id}`)
- migration `023_inbound_emails` applied
- a Resend `email.received` webhook pointing at `https://<render-api-host>/api/v1/webhooks/resend/inbound`

When `RESEND_INBOUND_DOMAIN` is set, outbound lead email sets `Reply-To` to `{organization-slug}@{RESEND_INBOUND_DOMAIN}` so customer replies hit that mailbox. The webhook returns 503 until the signing secret is set. A signed event is
stored only when exactly one `to` mailbox is
`{organization-slug}@{RESEND_INBOUND_DOMAIN}`. If the webhook payload has no
`text`/`html` and the API key is unset, the row is stored with a null body. This
repository does not create the Resend webhook.

## Local datastores

[Local Compose](../infra/docker-compose.yml) starts PostgreSQL and Redis for
development. Redis has no production queue or rate-limit role in the current
backend configuration.
