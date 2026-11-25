# FlowPilot Feature Status

This document summarizes the features present in the current repository. It is
based on the application code and configuration, not on deployment state or
future plans. “Completed” means the described capability exists; it does not
imply feature parity with third-party products. “Pending” means the capability
is not implemented or is blocked in the current codebase, not that it has an
approved delivery date.

## Completed

### Authentication and organizations

- Password-based registration and login, logout, active-organization
  selection, and browser sessions using an HTTP-only cookie.
- Organization-scoped memberships and roles, invitations, email verification,
  and password-reset flows.
- Tenant-owned resources are accessed through the authenticated organization
  context.

Google sign-in is implemented but requires provider configuration; see
[Optional and gated](#optional-and-gated).

### CRM and Sales Agent

- Tenant-scoped lead create, list, detail, and update, with lead status and
  source tracking.
- Tenant-scoped Company create, list, detail, update, archive, and restore,
  with role-based ownership and revision conflict handling.
- AI-assisted lead qualification and response-draft generation, followed by
  human review, editing, approval or rejection.
- Explicit sending of approved drafts, email-send history, follow-up scheduling
  and lifecycle management, and organization Activity.
- Sales Runs coordinate qualification and draft creation, with run history,
  cancellation, and explicit send and follow-up actions. Approval alone does
  not send an email.
- Website enquiry capture and lead creation, including embed and chat capture
  surfaces. Capture and automatic Sales Agent start are configuration-gated.

### Company Prospects

- Organization-scoped Company Prospect creation, listing, lifecycle changes,
  ICP fit scoring, and duplicate assessment.
- Company Prospects are distinct from Leads; discovery results do not become
  CRM records automatically.

### Deals and forecasting

- Deal records, stage changes, forecast categories, history, and controlled
  correction of closed-won amounts.
- Pipeline summaries and forecasts, organization sales targets, forecast
  scenarios, daily snapshots, and forecast-accuracy reporting.
- Forecasts are deterministic stage-probability calculations, not predictions
  trained on historical win rates. Amounts in other currencies are excluded
  rather than converted; reporting uses UTC calendar periods.

### Workflows

- Organization-scoped workflow rules and run history.
- Supported triggers are lead creation, inbound reply, and human-attention
  required. Supported actions are lead analysis, response drafting, and
  follow-up creation, subject to trigger/action validation.
- Workflow actions do not send email automatically.

### Generic webhooks

- Organization-scoped outgoing webhook endpoint management, secret rotation,
  test delivery, delivery history, and retry.
- Outbound events can be formatted for a Slack Incoming Webhook URL.

This is generic webhook delivery, not a native Slack connection or a native
integration with a CRM or another third-party workspace. See
[Optional and gated](#optional-and-gated) and [Pending or not implemented](#pending-or-not-implemented).

## Partially implemented

### Approvals

- The Approval Center is a draft-centric queue for generated lead-response
  drafts. Drafts can be reviewed and approved, rejected, or edited through the
  lead response-draft actions; sending remains a separate explicit action.
- Agent tool policy can record `REQUIRE_APPROVAL` decisions in tool-invocation
  history, but that is not a complete workflow for a person to resolve a tool
  approval and resume the execution.

### Inbox and analytics

- Inbox provides organization-scoped lead conversation list and detail views.
  It is not a general-purpose mailbox or a third-party email synchronization
  integration.
- Analytics provides a summary endpoint and corresponding UI, not a general
  analytics or reporting builder.

### Knowledge

- Users can manage organization-scoped knowledge entries, and eligible entries
  can be added as context for AI requests.
- Lexical retrieval is available. Optional embedding retrieval stores vectors
  as JSON on knowledge rows and ranks them in application code; it does not
  require pgvector.
- The current implementation is entry-based. File ingestion, content
  extraction, chunking, and a pgvector-backed retrieval pipeline are not
  present.

### Discovery and Company Prospect import

- Synthetic business discovery is read-only and returns explicitly marked
  synthetic results. A separate government-data search is available when
  enabled.
- The Company Prospect import route is source-gated. With no approved source
  configured, items are rejected; synthetic results are not imported.
- CSV lead preview and import are separate CRM capabilities and do not make
  synthetic Company Prospect discovery importable.

### Integrations

- Generic outbound webhooks are implemented, including Slack Incoming Webhook
  formatting. Resend supports outbound email and an inbound reply webhook
  path.
- These provider-specific paths do not provide native CRM or WhatsApp OAuth
  integrations or a native Slack app.

## Optional and gated

These capabilities have implementation code but require configuration,
external services, operator action, or external approval before use:

- **Google sign-in:** requires matching frontend and API OAuth client
  configuration.
- **AI features:** require a configured supported provider and its credentials.
  The available providers are OpenAI and Groq.
- **Email:** outbound sending and inbound replies depend on Resend settings;
  inbound delivery also requires a configured Resend webhook and domain.
- **Knowledge embeddings:** disabled by default; requires embedding-provider
  configuration. Lexical retrieval remains the fallback.
- **Government company-data search:** disabled by default and requires a
  server-side API key. Commercial use and quota permission require confirmation
  from the data provider; technical access alone is not permission.
- **Website capture:** off by default. Per-organization settings control
  capture; automatic Sales Agent start requires its separate worker and
  configuration.
- **Background workers:** the API does not start workers. A separate
  `python -m app.worker` process supports follow-up email, Sales Agent
  auto-start, workflow execution, outgoing webhooks, and forecast snapshots.
  Each loop is disabled by default and must be explicitly enabled and operated.
  Forecast snapshots can alternatively be captured by the repository's
  scheduled GitHub Actions workflow.
- **Outgoing webhooks:** delivery requires the separate webhook worker to be
  enabled and running.

## Pending or not implemented

The following should not be treated as available product capabilities in the
current codebase:

- Native OAuth integrations for third-party CRMs and WhatsApp. Generic
  webhooks do not provide those integrations.
- A complete human approval-and-resume lifecycle for AI tool invocations.
- Importing synthetic discovery results into Company Prospects. Import remains
  blocked unless a source is explicitly approved and configured.
- Document ingestion, content extraction, chunking, and a pgvector knowledge
  pipeline.

This list describes the repository’s current boundaries; it does not establish
commitments or timelines for future work.

## External dependencies and operational limits

- PostgreSQL is the application database. Background processing uses a
  separately operated worker that polls application data; Redis is not the
  production job queue.
- AI, email, OAuth, and government-data capabilities depend on their respective
  provider credentials and settings. Public website capture also depends on
  organization-level configuration.
- Contact-form and synthetic-discovery request limits use in-process state and
  are not shared across API instances. Website-capture limits are stored in
  PostgreSQL and shared across API processes.
- The forecasting model uses stage probabilities, single-currency amounts, and
  UTC calendar periods. It does not convert currency or use historical win
  rates.

## Implementation references

- [API router registry](../backend/app/api/v1/__init__.py)
- [Authentication routes](../backend/app/api/v1/auth.py)
- [Lead routes](../backend/app/api/v1/leads.py)
- [Company Prospect routes](../backend/app/api/v1/company_prospects.py)
- [Deal routes](../backend/app/api/v1/deals.py)
- [Pipeline and forecast routes](../backend/app/api/v1/pipeline.py)
- [Approvals routes](../backend/app/api/v1/approvals.py)
- [Inbox routes](../backend/app/api/v1/inbox.py)
- [Workflow model and supported triggers/actions](../backend/app/models/workflow.py)
- [Generic webhook routes](../backend/app/api/v1/integrations.py)
- [Worker entry point](../backend/app/worker/__main__.py)
- [Application settings and feature flags](../backend/app/core/config.py)
