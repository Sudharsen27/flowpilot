# Architecture

Living record of decisions for FlowPilot. Update this file when a decision changes.

## Product

Business operating platform: connect tools, give AI controlled capabilities, automate work, require approval for sensitive actions, and audit everything.

V1 is lead and customer automation. Other agent types reuse the same runtime later.

## System shape

Two applications in a monorepo:

- `frontend/` — Next.js UI. Components render; they do not own business rules.
- `backend/` — FastAPI API, services, and the follow-up worker process.

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

Only tools registered in `ToolRegistry` may run. Arguments are validated against the tool’s Pydantic schema before `execute()`. The model never writes to the database; tools run through `ToolExecutionService` with server-side tenant context. CRM, WhatsApp, calendar, Slack, webhooks, and other business integrations remain deferred. Approved lead-response **email** sending is a separate human-triggered API (Phase 4E), not a tool.

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
- **AgentExecution** — tenant-owned attempt: status (`QUEUED` / `RUNNING` / `COMPLETED` / `FAILED` / `CANCELLED`), JSON input/output, provider/model, timestamps, optional initiating user. `POST .../executions` commits `RUNNING`; `POST .../run` executes; `POST .../cancel` CAS-transitions `RUNNING` → `CANCELLED`. Abandoned `RUNNING` rows (process crash before a terminal CAS) are recovered to `FAILED` with `EXECUTION_ERROR` when they are older than the effective stale timeout. In-flight OpenAI HTTP calls are not aborted; the run loop stops at the next cooperative boundary.

Tenant isolation: repositories always query by `organization_id` from the authenticated membership JWT, never from the client body.

## Tool calling (Phase 3B)

`ToolRegistry` holds explicit `Tool` implementations. `ToolExecutionService` looks up the tool, validates arguments, applies policy, executes only on `ALLOW`, and writes a `ToolInvocation` audit row (organization, agent, execution, tool name, call id, risk, decision, status, argument keys, timestamps). Argument values are not stored.

`AIProvider.generate` may return internal `ToolCall` values. `OpenAIProvider` translates vendor tool definitions and tool-call payloads. `AgentExecutionService` runs a bounded loop (configurable `AGENT_MAX_TOOL_ITERATIONS`, default 3): text completes the run; tool calls go through the registry/service and results are sent back to the provider. There is no public tool-execution API.

`echo` is an in-process test/foundation tool, not a customer integration.

## Agent management API (Phase 3C)

```
Agent API
├── POST   /api/v1/agents                  Create (DRAFT)
├── GET    /api/v1/agents                  List (current org; optional status/type filters)
├── GET    /api/v1/agents/{id}             Get
├── PATCH  /api/v1/agents/{id}             Update configuration (not status)
├── POST   /api/v1/agents/{id}/ready       DRAFT → READY
├── POST   /api/v1/agents/{id}/activate    READY or PAUSED → ACTIVE
├── POST   /api/v1/agents/{id}/pause       ACTIVE → PAUSED
├── POST   /api/v1/agents/{id}/execute     Compatibility wrapper (start + run)
├── POST   /api/v1/agents/{id}/executions  Start (commit RUNNING)
├── POST   /api/v1/agents/{id}/executions/{execution_id}/run  Run a RUNNING execution
├── POST   /api/v1/agents/{id}/executions/{execution_id}/cancel  RUNNING → CANCELLED
├── GET    /api/v1/agents/{id}/executions  List executions (paginated summaries)
├── GET    /api/v1/agents/{id}/executions/{execution_id}  Execution detail
└── GET    /api/v1/agents/{id}/executions/{execution_id}/tool-invocations  Tool invocation audit
```

Tenant: organization is always the authenticated membership. Cross-tenant ids return 404. `OWNER` and `ADMIN` may create, update, and change lifecycle. `MEMBER` may list, get, execute eligible agents, cancel running executions, and read execution and tool-invocation history, but cannot change configuration or status.

PATCH does not accept `status`; lifecycle endpoints enforce allowed transitions. `NEEDS_ATTENTION` cannot be cleared by PATCH or those endpoints. Execution remains limited to `READY` and `ACTIVE`.

### Execution history (Phase 3H.1)

Authenticated members of the current organization may read persisted `AgentExecution` rows for agents they can already `GET`.

- `GET /api/v1/agents/{agent_id}/executions?limit=&offset=` — newest first (`created_at DESC`, `id DESC`). Default `limit` 20, minimum 1, maximum 50. Response: `{ items, limit, offset, total }`. List items are summaries (`id`, `status`, `provider`, `model`, timestamps, optional `input_preview` / `error_preview`). Full input, full output JSON, and `tool_results` are not returned.
- `GET /api/v1/agents/{agent_id}/executions/{execution_id}` — safe detail: input text, output text, provider, model, usage when stored, sanitized `error`, timestamps, `initiated_by_user_id`. Does not expose `tool_results`, raw provider payloads, or secrets.

Missing agents, missing executions, cross-tenant ids, and executions that belong to a different agent return 404. Unauthenticated requests return 401.

### Stuck RUNNING recovery (Phase 3L.3)

There is no worker or scheduler. Recovery is opportunistic and tenant-scoped: listing or loading an agent's executions, starting a new execution, running a specific execution, or listing its tool invocations CAS-updates matching rows.

A row is stale when `status = RUNNING` and `coalesce(started_at, created_at)` is at or before `now - timeout`. The timeout is `AGENT_EXECUTION_STALE_TIMEOUT_SECONDS` (default 300), raised to at least `(AGENT_MAX_TOOL_ITERATIONS + 1) * OPENAI_REQUEST_TIMEOUT_SECONDS` so a full in-process provider/tool loop is not treated as abandoned. There is no heartbeat column; a legitimate run that exceeds the effective timeout can be recovered as failed while `generate()` is still blocking. Existing `finalize_running` CAS still prevents a later `COMPLETED` write.

Recovery itself is `UPDATE … WHERE organization_id AND agent_id AND status = RUNNING AND timestamp ≤ cutoff` (optionally a single `execution_id`). It sets `FAILED`, sanitized error `This execution did not finish and was marked failed.`, `failure_category = EXECUTION_ERROR`, `completed_at`, and clears `output`. It never overwrites `COMPLETED`, `FAILED`, or `CANCELLED`. Re-running recovery is a no-op.

This does **not** guarantee crash recovery in the background. A crashed `RUNNING` row stays `RUNNING` until authenticated traffic for that organization and agent hits one of the operations above. There is no public “recover” API and no MEMBER-global sweep.

### Tool invocation history (Phase 3H.2)

`GET /api/v1/agents/{agent_id}/executions/{execution_id}/tool-invocations` lists `ToolInvocation` audit rows for one execution. `OWNER`, `ADMIN`, and `MEMBER` may read. Organization comes from the membership JWT.

Pagination matches execution history (`limit` default 20, min 1, max 50; `offset` ≥ 0). Ordering is chronological: `started_at ASC`, `id ASC`.

Public fields: `id`, `execution_id`, `agent_id`, `call_id`, `tool_name`, `risk_level`, `decision`, `status`, `argument_keys` (names only), `error`, timestamps. Argument values, tool outputs, `tool_results`, raw provider payloads, secrets, and stack traces are not returned. There is no per-invocation GET, Activity feed, or frontend history UI in this slice.

## Lead domain (Phase 4A)

`Lead` is an organization-owned sales record. It is independent of `AgentExecution`. Future sales-agent tools must call `LeadService` / `LeadRepository`; they must not write lead rows from the runtime loop.

Fields: `name` (required), optional `email` / `phone` / `company` / `notes`, `source`, `status`, timestamps. There is no score, AI qualification state, follow-up schedule, or activity feed in this slice. Email is **not** unique globally or inside an organization; duplicates are allowed so later qualification/merge can decide.

Status lifecycle (any of these may be set on create/update in V1; there is no enforced transition graph yet):

`NEW` → `CONTACTED` → `QUALIFIED` | `UNQUALIFIED` | `CONVERTED`

`UNQUALIFIED` means not a fit. `CONVERTED` means won. Pipeline `QUALIFIED` is not an AI score.

Sources: `MANUAL`, `WEBSITE`, `EMAIL`, `CHAT`, `API`, `IMPORT`.

```
Lead API
├── POST   /api/v1/leads
├── GET    /api/v1/leads                 List (q, status, source, limit, offset)
├── GET    /api/v1/leads/{lead_id}
├── PATCH  /api/v1/leads/{lead_id}
├── POST   /api/v1/leads/{lead_id}/qualify  AI enquiry analysis (does not mutate CRM status)
├── POST   /api/v1/leads/{lead_id}/respond  AI customer-response draft (does not send)
├── GET    /api/v1/leads/{lead_id}/response-drafts/{draft_id}
├── PATCH  /api/v1/leads/{lead_id}/response-drafts/{draft_id}
├── POST   /api/v1/leads/{lead_id}/response-drafts/{draft_id}/approve
├── POST   /api/v1/leads/{lead_id}/response-drafts/{draft_id}/reject
├── POST   /api/v1/leads/{lead_id}/response-drafts/{draft_id}/send
├── POST   /api/v1/leads/{lead_id}/follow-ups
├── GET    /api/v1/leads/{lead_id}/follow-ups
├── GET    /api/v1/leads/{lead_id}/follow-ups/{follow_up_id}
├── PATCH  /api/v1/leads/{lead_id}/follow-ups/{follow_up_id}
├── POST   /api/v1/leads/{lead_id}/follow-ups/{follow_up_id}/complete
└── POST   /api/v1/leads/{lead_id}/follow-ups/{follow_up_id}/cancel
```

Organization comes from the membership JWT. `organization_id` is not accepted from the client. Authenticated `OWNER`, `ADMIN`, and `MEMBER` may create, read, and update leads in their organization. Cross-tenant ids return 404. List pagination matches execution history (default 20, max 50, `created_at DESC`, `id DESC`). List responses include org-wide `status_counts` (not filtered by the current query) for overview metrics.

There is no Activity event model yet; lead writes do not emit activity rows.

## AI lead qualification (Phase 4B)

Lead CRUD remains usable without AI. Qualification is a separate operation:

`POST /api/v1/leads/{lead_id}/qualify` with `{ enquiry }`.

`OWNER`, `ADMIN`, and `MEMBER` may request it (same as other lead operations and agent execute). Organization comes from the JWT. Cross-tenant leads return 404.

The provider is invoked through `AIProvider.generate` with a JSON Schema `response_format` (OpenAI structured output). `LeadQualificationService` validates the result with Pydantic and drops extracted contact/company values that do not appear in the enquiry text. The model is instructed not to invent facts and to treat the enquiry as untrusted.

AI qualification (`QUALIFIED` / `UNQUALIFIED` / `NEEDS_MORE_INFORMATION`) is **not** CRM `Lead.status`. The CRM row is not updated. Analysis is stored in `lead_qualifications` (validated result JSON, provider/model, usage, duration, failure category). This is not an `AgentExecution`; agent history stays agent-scoped. No tools run for this endpoint.

`confidence` is a model self-report in `[0, 1]`, not a calibrated probability. List/detail include `latest_qualification` as a summary of the newest analysis row.

## AI lead response drafts (Phase 4C)

`POST /api/v1/leads/{lead_id}/respond` with `{ enquiry }` generates a customer-facing reply **draft**. Nothing is sent. `Lead.status` is not updated. No tools run. This is not an `AgentExecution`.

`LeadResponseDraftService` calls `AIProvider.generate` with a JSON Schema `{ "response": string }`. Failed and successful attempts are stored in `lead_response_drafts`. Retry creates a new row. List/detail include `latest_response_draft` for the newest **completed** draft.

If a completed `LeadQualification` exists for the same org/lead, a small validated analysis snapshot is passed as untrusted background context. The draft must not expose internal qualification fields to the customer.

## Human review of response drafts (Phase 4D)

Completed drafts have a review lifecycle on the same `lead_response_drafts` row: `GENERATED` → `EDITED` (optional) → `APPROVED` or `REJECTED`. The original AI text is stored in `original_response` and is never overwritten. `current_response` is what a human may edit. `revision` is an optimistic concurrency token (`expected_revision`); mismatches return 409.

`APPROVED` means a human approved that exact current text for **future** sending. It is not sent. Editing an approved draft clears the approval (`EDITED`). Rejected drafts stay persisted and cannot be edited or approved; generate a new draft instead. `Lead.status` is unchanged. There is no Activity event model; reviewer id and timestamps live on the draft row.

## Approved response email sending (Phase 4E)

Sending is a separate explicit action. Approval is not delivery.

`POST /api/v1/leads/{lead_id}/response-drafts/{draft_id}/send` (empty body) loads the lead and draft in the JWT organization, verifies persisted `review_status == APPROVED`, uses `lead.email` as the only recipient, uses `EMAIL_FROM_ADDRESS` / optional `EMAIL_FROM_NAME` as sender, and sends persisted `current_response` as plain text with subject `Re: Your enquiry`. The client cannot choose recipient, sender, or body.

`EmailProvider` is the send abstraction (same pattern as `AIProvider`). `ResendEmailProvider` is the first implementation (`RESEND_API_KEY`). Missing configuration returns the existing 503 `ProviderNotConfiguredError` after persisting a `FAILED` `CONFIGURATION_ERROR` row. Provider failures return 502 and persist `FAILED`. Missing lead email returns 422 and does not send.

History lives in `lead_email_sends` (`PENDING` → `SENT` or `FAILED`). `SENT` is recorded only after the provider call succeeds. Duplicate protection: a partial unique index on `(organization_id, response_draft_id, draft_revision)` for `PENDING`/`SENT`, plus Resend `Idempotency-Key` `{organization_id}:{draft_id}:{revision}`. A later approved revision may send again. Failed attempts may be retried. There is no automatic retry, no agent/tool send, and no background send.

Limitation: a crash after the provider accepts a message and before `SENT` is committed can still produce a duplicate on retry. Provider idempotency reduces but does not eliminate that window. This is not exactly-once delivery.

`OWNER`, `ADMIN`, and `MEMBER` may send. Cross-tenant ids return 404. `Lead.status` is not mutated. This is not an `AgentExecution` or `ToolInvocation`.

## Lead follow-ups (Phase 4F)

`LeadFollowUp` is a tenant-owned reminder row (`lead_follow_ups`), not a field on `Lead` or `LeadResponseDraft`. Types: `EMAIL_FOLLOW_UP`, `MANUAL_FOLLOW_UP`. Status: `PENDING` → `COMPLETED` or `CANCELLED` (terminal). `OVERDUE` is derived (`PENDING` and `due_at` before now) and is not persisted. Passing the due time does not complete the row and does not send email.

`EMAIL_FOLLOW_UP` stores a dedicated human-authored `body_text` (required, trimmed, max 8000). This is not `notes`. `MANUAL_FOLLOW_UP` does not require `body_text`. Existing rows may have NULL `body_text`; new EMAIL follow-ups cannot. Only `PENDING` rows may be edited.

Create/list/get/patch plus explicit complete/cancel. `due_at` is timezone-aware UTC. List order is `due_at ASC`, `id ASC` (default 20, max 50). Optional `email_send_id` must be a `SENT` send for the same org and lead. Optimistic `revision` / `expected_revision` returns 409 on stale lifecycle actions. There is no Activity model; timestamps on the row are the audit trail.

Due follow-ups are **not** executed automatically. No cron, workers, agent runs, or Resend calls from this domain. Storing `body_text` does not schedule or send mail.

`LeadFollowUpExecution` (`lead_follow_ups` vs `lead_follow_up_executions`) is a separate tenant-owned attempt row. Status: `PENDING` → `RUNNING` → `SENT` or `FAILED`. `LeadFollowUp` status is unchanged. Snapshots (`recipient_email`, `sender_email`, `subject`, `body_text`) are frozen per attempt. Unique `(follow_up_id, attempt)`; at most one `PENDING`/`RUNNING` execution per follow-up. Future provider idempotency key shape: `follow-up:{follow_up_id}:attempt:{attempt}`. Claiming uses `SELECT … FOR UPDATE SKIP LOCKED` on PostgreSQL, then commits before any provider call. This is not exactly-once delivery. There is no worker, polling, or send in this slice.

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

## Phase 3C (agent management API)

Tenant-safe agent CRUD and lifecycle (`ready` / `activate` / `pause`). `OWNER`/`ADMIN` configure agents; `MEMBER` can read and execute eligible agents. Status is not mutated via PATCH.

## Phase 3H.1 (execution history read APIs)

Paginated list and safe detail over existing `AgentExecution` rows. No Activity feed or frontend history UI in this slice.

## Phase 3H.2 (tool invocation history read API)

Paginated, chronological list of `ToolInvocation` audit rows for a specific execution. Argument values and tool outputs are not exposed.

## Phase 4A (lead domain foundation)

Organization-owned `Lead` model and CRUD APIs, connected to the existing Leads screen. No AI qualification, scoring, or sales-agent tools.

## Phase 4B (AI lead understanding)

Structured enquiry analysis via `AIProvider` JSON Schema output, stored on `lead_qualifications`. Does not mutate `Lead.status` or run tools.

## Phase 4C (AI lead response drafting)

Structured customer-facing reply drafts via `AIProvider` JSON Schema `{ response }`, stored on `lead_response_drafts`. Does not send messages, mutate `Lead.status`, or run tools.

## Phase 4D (human approval and editing)

Humans edit, approve, or reject a completed response draft. Original AI text is preserved. Approval is not sending.

## Phase 4E (approved email sending)

Humans send an approved draft by email. Sending is an explicit external side effect. Approval is not sending. Sent means the email provider confirmed acceptance.

## Phase 4F (lead follow-up scheduling)

Humans create, list, reschedule, complete, and cancel follow-ups. Overdue is derived. EMAIL follow-ups require stored `body_text`. Due follow-ups are not sent or executed automatically.

## Phase 4G (automated follow-up execution)

`LeadFollowUpExecution` persists automated EMAIL follow-up attempts. `LeadFollowUpExecutionService.execute_follow_up(organization_id, follow_up_id)` is the single send path: claim, snapshot, `EmailProvider.send`, SENT/FAILED, then COMPLETED. MANUAL follow-ups are never emailed.

### Worker process

A dedicated polling process (`python -m app.worker`) discovers due EMAIL follow-ups and calls that service. The FastAPI application never starts it: no startup hook, no `BackgroundTasks`, no in-process loop. Celery, RQ, APScheduler, Redis queues, and cron are not used.

```
LeadFollowUp (PENDING, EMAIL_FOLLOW_UP, due_at <= now)
    → PostgreSQL SELECT ... FOR UPDATE SKIP LOCKED
    → LeadFollowUpExecution RUNNING (commit)
    → EmailProvider.send (outside the DB transaction)
    → execution SENT or FAILED (commit)
    → follow-up COMPLETED only after SENT (commit)
```

- **Discovery** is organization-independent and read-only. Tenant identity always comes from the claimed row, never from an HTTP request.
- **Claiming** uses `FOR UPDATE SKIP LOCKED` plus the partial unique index on in-flight executions. Two workers cannot send the same follow-up concurrently. SQLite tests do not prove SKIP LOCKED; PostgreSQL tests do.
- **Batching** is `FOLLOW_UP_WORKER_BATCH_SIZE` (default 10). One failed item is logged and the rest of the batch continues. There are no automatic retries: FAILED leaves the follow-up PENDING.
- **Shutdown** handles SIGINT/SIGTERM: stop taking new work, finish the in-flight item, exit. Sleep is interruptible.
- **Configuration** (disabled by default): `FOLLOW_UP_WORKER_ENABLED`, `FOLLOW_UP_WORKER_POLL_INTERVAL_SECONDS` (30), `FOLLOW_UP_WORKER_BATCH_SIZE` (10).
- **Delivery is at-least-once.** If the provider accepts an email and the process dies before SENT commits, a later attempt may send again. The provider idempotency key `follow-up:{id}:attempt:{n}` is the duplicate-acceptance protection. This is not exactly-once delivery.
- There is no public worker API (`/run-due-follow-ups` and similar do not exist). Humans inspect follow-ups through the authenticated operations list.

## Design system (Phase 5A)

FlowPilot UI uses Tailwind v4 tokens in `frontend/app/globals.css`, shadcn/ui, and Lucide. Domain statuses map through `frontend/lib/status.ts` onto one `StatusBadge` semantic language; wrappers keep domain labels. AI origin is marked with `AiBadge` (Generated / Suggested / Analysis / Processing / Agent), not glow or decorative effects. Confirm destructive or irreversible actions with `ConfirmDialog`. Dark-mode tokens exist for future theming; there is no theme toggle yet.
