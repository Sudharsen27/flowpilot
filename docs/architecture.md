# Architecture

Living record of decisions for the AI Business Automation Platform. Update this file when a decision changes.

## Product

Business operating platform: connect tools, give AI controlled capabilities, automate work, require approval for sensitive actions, and audit everything.

V1 is lead and customer automation. Other agent types reuse the same runtime later.

## System shape

Two applications in a monorepo:

- `frontend/` — Next.js UI. Components render; they do not own business rules.
- `backend/` — FastAPI API, services, and (later) workers.

Request path:

`UI → API client → API → services → domain → repositories → PostgreSQL`

AI path (later phases):

`Agent → context → decision → tool selection → policy → execute or approve → verify → audit`

The model never writes to the database. Tools call application services.

## Multi-tenancy

Every business-owned row carries `organization_id`. Repositories always filter by tenant. Cross-organization access is a defect.

## Safety

Each tool will declare name, description, input/output schemas, required permissions, and risk (`LOW` / `MEDIUM` / `HIGH` / `CRITICAL`). HIGH and CRITICAL actions require human approval. Policy cannot be bypassed by the model.

## LLM providers

`LLMProvider` and `EmbeddingProvider` interfaces. OpenAI is the first implementation. Product code depends on the interface, not a vendor SDK.

## Workflows

Versioned graphs (nodes, edges, trigger) plus execution records in Postgres. V1 will interpret graphs in-process. A durable orchestrator can replace the runner later without rewriting the domain model.

## Knowledge

Ingest → extract → chunk → embed → pgvector → retrieve → context. Users see Knowledge, not vector internals.

## Observability

Metrics come from real execution traces (latency, tokens, cost, approvals, outcomes). No placeholder analytics.

## Local infrastructure

`infra/docker-compose.yml` runs PostgreSQL 16 with pgvector, and Redis. Application containers are not part of the foundation scaffold.

## Phase 0 (this scaffold)

Git, environment templates, Compose, FastAPI `/health`, Next.js app shell with primary navigation, lint/format/typecheck. No auth, agents, models, or product features.
