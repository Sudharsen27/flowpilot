# Architecture

Living record of decisions for FlowPilot. Update this file when a decision changes.

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

## Multi-tenancy and identity

Every business-owned row carries `organization_id`. Repositories that load tenant resources take `organization_id` first:

`get_resource(organization_id, resource_id)`

Do not authorize from a client-supplied organization id. Tenant context comes from the authenticated membership in the JWT (`org` and `membership` claims), then is re-loaded from the database.

### Models

- **Organization** — `id`, `name`, unique `slug`, timestamps.
- **User** — `id`, unique `email`, `name`, `password_hash`, timestamps. Users can belong to multiple organizations via memberships.
- **Membership** — `id`, `organization_id`, `user_id`, `role`, `created_at`. Unique on `(organization_id, user_id)`.

Roles: `OWNER`, `ADMIN`, `MEMBER`. Registration creates an organization and an `OWNER` membership.

### Authentication

- Passwords are hashed with Argon2. `password_hash` is never returned by the API.
- Access tokens are JWTs issued after register/login. Token handling lives in `app/core/security.py`.
- `SECRET_KEY` may use a development default only when `ENVIRONMENT` is `development` or `test`. Other environments require a unique secret of at least 32 characters.
- Dependencies: `get_current_user`, `get_current_membership`, `get_current_organization`.
- The frontend waits for `/api/v1/users/me` before rendering product routes. Guests are redirected to `/login`; authenticated users are redirected away from login and registration.
- Frontend session state preserves the current user, organization, and membership. Roles inform presentation only; the backend remains authoritative for authorization.
- Browser localStorage is retained only as a development foundation. Production authentication requires a safer session mechanism, such as secure httpOnly cookies, before release.

### Repository conventions

- `UserRepository` is global (email uniqueness is global).
- `OrganizationRepository` looks up organizations by id or slug.
- `MembershipRepository` scopes membership reads by `organization_id`. Listing members is always `list_for_organization(organization_id)`.

## Safety

Each tool will declare name, description, input/output schemas, required permissions, and risk (`LOW` / `MEDIUM` / `HIGH` / `CRITICAL`). HIGH and CRITICAL actions require human approval. Policy cannot be bypassed by the model.

## AI runtime (Phase 3A)

Authenticated API requests run a tenant-owned **Agent** through an **AgentExecutionService**. The service loads the agent for the caller's organization, records an **AgentExecution**, and calls an **AIProvider**. Product and service code depend on the `AIProvider` protocol, not a vendor SDK. **OpenAIProvider** is the first implementation (`OPENAI_API_KEY`, `OPENAI_MODEL`).

This slice only produces a structured AI response and an audit row. External tool execution, CRM/email/WhatsApp/calendar actions, webhooks, workflow runners, RAG, and autonomous background agents are deferred.

### Models

- **Agent** — tenant-owned (`organization_id`). Types: `SALES`, `SUPPORT`, `OPERATIONS`, `COMMUNICATION`. Statuses: `DRAFT`, `READY`, `ACTIVE`, `PAUSED`, `NEEDS_ATTENTION`. Only `READY` and `ACTIVE` may execute.
- **AgentExecution** — tenant-owned attempt: status (`QUEUED` / `RUNNING` / `COMPLETED` / `FAILED`), JSON input/output, provider/model, timestamps, optional initiating user.

Tenant isolation: repositories always query by `organization_id` from the authenticated membership JWT, never from the client body.

## LLM providers

`AIProvider` (text generation) is the current runtime interface. `EmbeddingProvider` remains planned for knowledge retrieval. OpenAI is the first `AIProvider` implementation.

## Workflows

Versioned graphs (nodes, edges, trigger) plus execution records in Postgres. V1 will interpret graphs in-process. A durable orchestrator can replace the runner later without rewriting the domain model.

## Knowledge

Ingest → extract → chunk → embed → pgvector → retrieve → context. Users see Knowledge, not vector internals.

## Observability

Metrics come from real execution traces (latency, tokens, cost, approvals, outcomes). No placeholder analytics.

## Local infrastructure

`infra/docker-compose.yml` runs PostgreSQL 16 with pgvector, and Redis. Application containers are not part of the foundation scaffold.

## Phase 1 (tenant and identity)

PostgreSQL/SQLAlchemy/Alembic, Organization/User/Membership, Argon2 passwords, JWT auth, tenant-safe membership lookups, register/login/me/current-org APIs, and tests including tenant isolation. No agents, leads, RAG, or workflows.

## Phase 2, Slice 1 (authenticated app shell)

Product routes are guarded by a client-side authentication boundary that waits for session restoration before rendering the shell. Login and registration are guest-only routes. The session preserves user, organization, and membership context; logout clears both in-memory and stored authentication state before redirecting to login. This remains a development-only localStorage session architecture.

## Phase 2, Slice 3 (global application chrome)

Every authenticated route uses one `AppShell`: a persistent grouped sidebar on desktop, the existing focus-managed navigation drawer below desktop, an authenticated top bar, and a shared responsive `PageContainer`. Navigation metadata and nested-route active matching live in `lib/navigation.ts`.

The top bar reads the current organization, user, and membership role from `AuthProvider`. Its user menu delegates logout to the existing auth mechanism. Global search is an honest UI entry point only; product search, notifications, organization switching, and business data remain outside the shell.

## Phase 3A (AI runtime foundation)

Tenant-owned `Agent` and `AgentExecution` models, `AIProvider` / `OpenAIProvider`, `AgentExecutionService`, and authenticated `POST /api/v1/agents/{agent_id}/execute`. No tool calling, workflows, or external business actions.
