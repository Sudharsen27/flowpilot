# FlowPilot

Business operating platform for AI-powered lead and customer automation.

This repository has completed **Phase 5E**: Sales Agent work is visible from the Leads directory and a read-only Sales Agent history dialog. History composes existing SalesRun, qualification, draft, email-send, and follow-up records. There is no Activity system. SalesRun mutations stay on the Sales Agent. Follow-up management stays on the existing follow-up UI.

## Requirements

- Python 3.12+
- Node.js 20+
- npm
- Docker (PostgreSQL + Redis). Tests use an in-memory SQLite database and do not require Docker.

## Setup

```bash
cp .env.example .env
```

### Datastores

```bash
docker compose -f infra/docker-compose.yml up -d
cd backend
alembic upgrade head
```

### Backend

```bash
source .venv/bin/activate
pip install -e "./backend[dev]"
cd backend
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

- Health: [http://localhost:8000/health](http://localhost:8000/health)
- Register: `POST /api/v1/auth/register`
- Login: `POST /api/v1/auth/login`
- Current user: `GET /api/v1/users/me`
- Execute agent (authenticated): `POST /api/v1/agents/{agent_id}/execute`
- Start sales run (authenticated, SALES agents): `POST /api/v1/agents/{agent_id}/sales-runs`
- Send approved sales run (authenticated): `POST /api/v1/agents/{agent_id}/sales-runs/{sales_run_id}/send`
- Schedule sales run follow-up (authenticated): `POST /api/v1/agents/{agent_id}/sales-runs/{sales_run_id}/schedule-follow-up`
- Lead Sales Agent history (authenticated): `GET /api/v1/leads/{lead_id}/sales-runs`
- Qualification detail (authenticated): `GET /api/v1/leads/{lead_id}/qualifications/{qualification_id}`

The follow-up worker is a separate process. It is disabled by default and is never started by the API:

```bash
FOLLOW_UP_WORKER_ENABLED=true python -m app.worker
```

`OPENAI_API_KEY` and `OPENAI_MODEL` are documented in `.env.example`. Unit tests mock `AIProvider` and do not call OpenAI.

### Frontend

```bash
cd frontend
npm install
npm run dev
```

App: [http://localhost:3000](http://localhost:3000) (or the port Next.js prints if 3000 is already in use)

Sign in: [http://localhost:3000/login](http://localhost:3000/login)

Browser tokens are stored in local storage for local development. That is not a production session design.

## Checks

```bash
# From repo root
pytest
cd backend && ruff check app tests && mypy app

# From frontend/
npm run lint
npm run typecheck
npm run build
```

## Architecture

See [docs/architecture.md](docs/architecture.md).
