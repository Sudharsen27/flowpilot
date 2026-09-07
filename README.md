# AI Business Automation Platform

Premium business operating platform for AI-powered lead and customer automation.

This repository is in **Phase 0 (foundation)**. The API serves a health check. The UI is an empty application shell.

## Requirements

- Python 3.12+
- Node.js 20+ (this machine has Node 24)
- npm
- Docker (for PostgreSQL + Redis). Docker is not required to run the health API or the UI.

## Setup

```bash
cp .env.example .env
```

### Backend

```bash
source .venv/bin/activate   # existing venv, or: python3.12 -m venv .venv
pip install -e "./backend[dev]"
cd backend
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Health: [http://localhost:8000/health](http://localhost:8000/health)

### Frontend

```bash
cd frontend
npm install
npm run dev
```

App: [http://localhost:3000](http://localhost:3000)

### Datastores (optional in Phase 0)

Requires Docker or Colima.

```bash
docker compose -f infra/docker-compose.yml up -d
```

## Checks

```bash
# Backend (from backend/)
pytest
ruff check app tests
mypy app

# Frontend (from frontend/)
npm run lint
npm run typecheck
```

## Architecture

See [docs/architecture.md](docs/architecture.md).
