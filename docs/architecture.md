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

AI path:

```
AI Runtime
    → AI Provider
    → Tool Call
    → Tool Registry
    → Policy (ALLOW | REQUIRE_APPROVAL | DENY)
    → Tool Execution
    → Tool Result
    → AI Runtime
```

Only tools registered in `ToolRegistry` may run. Arguments are validated against the tool’s Pydantic schema before `execute()`. The model never writes to the database; tools run through `ToolExecutionService` with server-side tenant context. External CRM, email, WhatsApp, calendar, Slack, webhooks, and other business integrations are deferred.

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

Each registered tool declares name, description, input/output schemas, and risk (`LOW` / `MEDIUM` / `HIGH`). `DefaultToolPolicy` allows `LOW` tools and returns `REQUIRE_APPROVAL` for `MEDIUM` and `HIGH`. Tools are not executed on `REQUIRE_APPROVAL` or `DENY`. A full Approvals backend is not in this slice; the decision is recorded on `ToolInvocation`. Policy cannot be bypassed by the model.

## AI runtime (Phase 3A)

Authenticated API requests run a tenant-owned **Agent** through an **AgentExecutionService**. The service loads the agent for the caller's organization, records an **AgentExecution**, and calls an **AIProvider**. Product and service code depend on the `AIProvider` protocol, not a vendor SDK. **OpenAIProvider** is the first implementation (`OPENAI_API_KEY`, `OPENAI_MODEL`).

This slice produces a structured AI response and an audit row. Tool calling is described in Phase 3B.

### Models

- **Agent** — tenant-owned (`organization_id`). Types: `SALES`, `SUPPORT`, `OPERATIONS`, `COMMUNICATION`. Statuses: `DRAFT`, `READY`, `ACTIVE`, `PAUSED`, `NEEDS_ATTENTION`. Only `READY` and `ACTIVE` may execute.
- **AgentExecution** — tenant-owned attempt: status (`QUEUED` / `RUNNING` / `COMPLETED` / `FAILED`), JSON input/output, provider/model, timestamps, optional initiating user.

Tenant isolation: repositories always query by `organization_id` from the authenticated membership JWT, never from the client body.

## Tool calling (Phase 3B)

`ToolRegistry` holds explicit `Tool` implementations. `ToolExecutionService` looks up the tool, validates arguments, applies policy, executes only on `ALLOW`, and writes a `ToolInvocation` audit row (organization, agent, execution, tool name, call id, risk, decision, status, argument keys, timestamps). Argument values are not stored.

`AIProvider.generate` may return internal `ToolCall` values. `OpenAIProvider` translates vendor tool definitions and tool-call payloads. `AgentExecutionService` runs a bounded loop (configurable `AGENT_MAX_TOOL_ITERATIONS`, default 3): text completes the run; tool calls go through the registry/service and results are sent back to the provider. There is no public tool-execution API.

`echo` is an in-process test/foundation tool, not a customer integration.

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

Tenant-owned `Agent` and `AgentExecution` models, `AIProvider` / `OpenAIProvider`, `AgentExecutionService`, and authenticated `POST /api/v1/agents/{agent_id}/execute`.

## Phase 3B (AI tool calling foundation)

Registered tools, input validation, risk/policy (`ALLOW` / `REQUIRE_APPROVAL` / `DENY`), `ToolInvocation` audit rows, OpenAI tool-call translation, and a strictly limited execution loop. No real external business integrations.
