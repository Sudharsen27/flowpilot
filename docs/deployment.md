# Production deployment

FlowPilot runs as three processes against one PostgreSQL database:

- Frontend on Vercel
- API on Render
- Worker on Render
- PostgreSQL on Render

The API process does not start the worker. Redis is present in local Compose and is not part of this production process model.

## Frontend (Vercel)

Set `NEXT_PUBLIC_API_URL` to the public Render API origin, including the scheme and without a trailing path. A production build fails when this variable is missing. Do not put backend secrets in frontend environment variables.

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
- `DATABASE_URL` — Render PostgreSQL URL using the `postgresql+psycopg://` driver
- `CORS_ORIGINS` — the Vercel origin, `https://` only, no localhost and no `*`
- `AI_PROVIDER` — `openai` or `groq`
- The matching provider key and model when that provider should be used
- `TYPESAFE_API_KEY` when human decision calls should run
- `RESEND_API_KEY`, `EMAIL_FROM_ADDRESS`, and `EMAIL_FROM_NAME` when email should send

Missing AI or email credentials do not stop the API. Settings shows those integrations as not configured. Missing `SECRET_KEY`, a local `DATABASE_URL`, or a non-HTTPS CORS origin prevents production startup.

Health:

- `GET /health` — liveness. It does not check PostgreSQL.
- `GET /health/ready` — readiness. It checks database connectivity and returns 503 without connection details when PostgreSQL is unavailable.

## Worker (Render background worker)

Use the same repository, build, and environment as the API, including `DATABASE_URL`. Do not give the worker a public HTTP service. Do not run `uvicorn` in this service.

Start command:

```bash
cd backend && python -m app.worker
```

Enable the loops this process should run:

- `FOLLOW_UP_WORKER_ENABLED=true` for due follow-up email
- `SALES_AGENT_AUTO_START_WORKER_ENABLED=true` for website-enquiry Sales Agent starts

If both flags are false, the process exits immediately. Leave both false on the API service. The worker does not use Celery, Redis, or another queue.

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
