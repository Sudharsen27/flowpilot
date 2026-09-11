# FlowPilot

Business operating platform for AI-powered lead and customer automation.

This repository has completed **Phase 2 product UI foundations**. Phase 3A adds a tenant-safe AI runtime (Agent, AgentExecution, AIProvider) without tool calling or external business actions.

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

App: [http://localhost:3000](http://localhost:3000)

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
