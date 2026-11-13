# Production deployment

FlowPilot runs as three processes against one PostgreSQL database:

- Frontend on Vercel
- API on Render
- Worker on Render
- PostgreSQL on Neon

The API process does not start the worker. Redis is present in local Compose and is not part of this production process model.

## Frontend (Vercel)

Set `NEXT_PUBLIC_API_URL` to the public Render API origin, including the scheme and without a trailing path. A production build fails when this variable is missing. Do not put backend secrets in frontend environment variables.

Optional: set `NEXT_PUBLIC_SITE_URL` to the public marketing origin (scheme + host, no path) after the production hostname is known. The frontend uses it for canonical URLs, Open Graph page URLs, `robots.txt` sitemap, and `sitemap.xml`. Localhost and common preview hosts are rejected. Leave it unset rather than inventing a hostname.

Optional Google sign-in: set `NEXT_PUBLIC_GOOGLE_CLIENT_ID` to the same OAuth Web client id used by the API. Authorized JavaScript origins in Google Cloud Console must include the Vercel origin. Do not put `GOOGLE_OAUTH_CLIENT_SECRET` in frontend env.

## API (Render web service)

Root directory: repository root.

Build:

```bash
pip install "./backend[dev]"
```

Production install can omit the dev extra:

```bash
pip install ./backend
```

Pre-deploy command:

```bash
cd backend && alembic upgrade head
```

Start command:

```bash
cd backend && uvicorn app.main:app --host 0.0.0.0 --port "$PORT"
```

`alembic upgrade head` stays a separate deployment step. It is not part of API startup. A failed migration stops the deploy before the new API revision serves traffic. Do not run schema changes from a request handler.

Required environment:

- `ENVIRONMENT=production`
- `SECRET_KEY` — unique, at least 32 characters, not the example value
- `DATABASE_URL` — Neon PostgreSQL connection string, including `sslmode=require`. A `postgresql://` or `postgres://` URL is switched to the `postgresql+psycopg://` driver automatically
- `CORS_ORIGINS` — the Vercel origin, `https://` only, no localhost and no `*`
- Public website capture limits are stored in PostgreSQL (migration `045_website_capture_attempts`) and shared across API processes. `WEBSITE_CAPTURE_RATE_LIMIT_MAX` and `WEBSITE_CAPTURE_RATE_LIMIT_WINDOW_SECONDS` keep their defaults of 5 and 60. `WEBSITE_CAPTURE_DAILY_ENQUIRY_CAP` defaults to 100 enquiries per organization per UTC day and is optional.
- `AI_PROVIDER` — `openai` or `groq`
- The matching provider key and model when that provider should be used
- `TYPESAFE_API_KEY` when human decision calls should run
- `RESEND_API_KEY`, `EMAIL_FROM_ADDRESS`, and `EMAIL_FROM_NAME` when email should send
- The same Resend settings for `POST /api/v1/public/contact`. `EMAIL_FROM_ADDRESS` must be on a domain verified with Resend. Notifications go only to `hello.sundardigital@gmail.com`. `CONTACT_RATE_LIMIT_MAX` and `CONTACT_RATE_LIMIT_WINDOW_SECONDS` tune the in-process limit; they do not provide a shared limit across API instances.
- Optional Google sign-in: `GOOGLE_OAUTH_CLIENT_ID` and `GOOGLE_OAUTH_CLIENT_SECRET` for `POST /api/v1/auth/google`. The API exchanges GIS popup codes with `redirect_uri=postmessage`. Missing values return 503 from that route only.

Missing AI, email, or Google OAuth credentials do not stop the API. Settings shows those integrations as not configured. Missing `SECRET_KEY`, a local `DATABASE_URL`, or a non-HTTPS CORS origin prevents production startup.

Health:

- `GET /health` — liveness. It does not check PostgreSQL.
- `GET /health/ready` — readiness. It checks database connectivity and returns 503 without connection details when PostgreSQL is unavailable.

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

Use the same repository, build, and environment as the API, including `DATABASE_URL`. Do not give the worker a public HTTP service. Do not run `uvicorn` in this service.

Start command:

```bash
cd backend && python -m app.worker
```

Enable the loops this process should run:

- `FOLLOW_UP_WORKER_ENABLED=true` for due follow-up email
- `SALES_AGENT_AUTO_START_WORKER_ENABLED=true` for website-enquiry Sales Agent starts
- `WORKFLOW_WORKER_ENABLED=true` for workflow rules
- `WEBHOOK_WORKER_ENABLED=true` for outgoing webhook deliveries
- `FORECAST_SNAPSHOT_WORKER_ENABLED=true` for the daily forecast snapshots used by forecast accuracy. Optional: `FORECAST_SNAPSHOT_WORKER_POLL_INTERVAL_SECONDS` (default 300) and `FORECAST_SNAPSHOT_WORKER_BATCH_SIZE` (default 100). Needs migration `038_forecast_snapshots`. Instead of this flag, snapshots can run on the free GitHub Actions schedule below.

If all of these flags are false, the process exits immediately. Leave all of them false on the API service. The worker does not use Celery, Redis, or another queue.

## Forecast snapshots (GitHub Actions)

`.github/workflows/forecast-snapshots.yml` captures the daily forecast snapshots without a paid background worker. It runs the one-off runner:

```bash
cd backend && python -m app.worker.forecast_snapshot_once
```

The runner captures every organization that has no snapshot for today (UTC), in batches of `FORECAST_SNAPSHOT_WORKER_BATCH_SIZE` (default 100), prints one line of counts and exits: 0 when the lookup and every capture succeeded, 1 otherwise. It does not read `FORECAST_SNAPSHOT_WORKER_ENABLED`. Capture is idempotent per organization and UTC day, so repeated, overlapping or manual runs never add a second snapshot. A failed organization is normally left for the next run; in a long run it can be tried again once its five-minute retry delay has passed. If the organization lookup, or the retry check after a batch, fails, the run exits 1 and its summary may not include that batch's counts.

Schedule: four runs a day at 00:17, 06:17, 12:17 and 18:17 UTC, plus manual runs (Actions → Forecast snapshots → Run workflow). The 00:17 run captures the day; the others catch up after a dropped, delayed or failed run, and do nothing once every organization has today's snapshot. The workflow has no push or pull-request trigger, runs only on `main`, has read-only repository permissions, a 10-minute timeout, and never cancels a run in progress.

Setup (repository Settings, once):

1. Settings → Environments → New environment, named `production`.
2. Deployment branches and tags → Selected branches and tags → add `main` only.
3. Environment secrets:
   - `DATABASE_URL` — the Neon production connection string, the same database as the API (`sslmode=require`).
   - `SECRET_KEY` — a newly generated value of at least 32 characters used only by this job, for example from `python -c "import secrets; print(secrets.token_urlsafe(48))"` run locally. The job signs no tokens; never reuse or paste the API's `SECRET_KEY`.
4. Environment variable (not a secret): `CORS_ORIGINS` — the production Vercel origin, `https://` only, the same value as the API's. Production settings refuse to start without it.

A preliminary step fails with the names, never the values, of any missing setting. Do not add steps that print environment variables, and do not enable debug logging for this workflow.

The repository is public, so workflow logs are public. The runner's output is counts only: no organization ids, figures, SQL parameters, connection details, exception messages or tracebacks; an error inside the runner names only its class. Invalid settings (for example a short `SECRET_KEY` or a non-HTTPS `CORS_ORIGINS`) can fail before the runner starts, with a short Pydantic validation traceback; its message is redacted and never contains the supplied values. To check a run, open Actions → Forecast snapshots and read the last line of "Capture forecast snapshots":

- `status=complete … failed=0 lookup_failed=false` — every organization has today's snapshot.
- `status=failed` with `failed=N` — N captures failed; the next run retries them.
- `status=failed … lookup_failed=true`, `status=error error=<Class>`, or a `ValidationError` for `Settings` — the database or the settings are unreachable or invalid. Check the environment secrets and variable, and that migration `038_forecast_snapshots` is applied.

GitHub emails the workflow's owner about failed scheduled runs. Scheduled runs can start late or, rarely, be skipped; the later runs cover them. GitHub disables scheduled workflows in a public repository after 60 days without repository activity; re-enable it from the Actions tab. The missing-snapshot query below confirms coverage.

The Render background worker may still be needed for follow-up email, Sales Agent auto-start, workflow rules or outgoing webhooks. Before removing that service or turning off `FORECAST_SNAPSHOT_WORKER_ENABLED` on it, check which of its worker flags are `true`, and confirm a successful GitHub Actions run and a zero result from the query below. Both may run at once safely.

Forecast snapshots are captured once per organization per UTC day; the worker logs `forecast snapshots complete date=YYYY-MM-DD` when every organization has one and none is waiting for a retry. To see how many organizations still lack today's snapshot:

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

Apply migrations with the API pre-deploy command before the new web release starts. Run one migration at a time; do not start two API deploys that both execute `alembic upgrade head`.

Failure: Render stops the deploy when the pre-deploy command exits non-zero. The previous API release keeps serving. Fix the migration or the database URL, then deploy again.

Rollback: deploy the previous application release only when its code still matches the current schema. Alembic downgrade is a manual, reviewed step and is not part of the start command. Do not generate a new revision during a routine deploy.

## Inbound email

The public webhook is `POST /api/v1/webhooks/resend/inbound`. Production is not receiving inbound mail. Turning it on later requires every one of these:

- `RESEND_WEBHOOK_SECRET` set on the API service to the Resend webhook signing secret
- `RESEND_INBOUND_DOMAIN` set on the API service to the domain whose recipient local-part equals an organization slug, such as `acme@inbound.example.com`
- migration `023_inbound_emails` applied before that API release starts
- a Resend `email.received` webhook pointing at `https://<render-api-host>/api/v1/webhooks/resend/inbound`

Leave the secret and domain unset until that route exists. Outbound mail does not use them. The webhook returns 503 until the signing secret is set. A signed event is stored only when exactly one `to` mailbox is `{organization-slug}@{RESEND_INBOUND_DOMAIN}`. This repository does not create the Resend webhook.

## Local datastores

`infra/docker-compose.yml` starts PostgreSQL and Redis for local development. It is not the production topology.
